#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recette finale — Phase 5 : la chaîne temps réel, scénario par scénario.

Rejoue ce que `html_tests/simulation-control.html` pilote à la main :
  1. cycle de trajet complet (démarrage AVEC géométrie → MS11 armé, /route, fin) ;
  2. non-idempotence du démarrage (le cas que la file hors ligne réconcilie) ;
  3. VITESSE_EXCESSIVE (règle live MS11) ;
  4. DEVIATION_ITINERAIRE — la seule règle qui exige la route figée (piège n° 12) ;
  5. incident MS10 → RabbitMQ → notification MS4 ;
  6. profondeur des files RabbitMQ orphelines (dette mesurée).

Usage : python scripts/recette/temps_reel.py
Sortie : scripts/recette/resultats/temps_reel.json
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
import time

import requests

for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RACINE = pathlib.Path(__file__).resolve().parents[2]
SORTIE = RACINE / "scripts" / "recette" / "resultats" / "temps_reel.json"
GW, MS11 = "http://localhost:8080", "http://localhost:8091"
RABBIT = "http://localhost:15672/api/queues"

resultats: list[dict] = []
_ecarts = 0


def note(nom, attendu, obtenu, ok, commentaire=""):
    global _ecarts
    _ecarts += (not ok)
    resultats.append({"nom": nom, "attendu": attendu, "obtenu": obtenu,
                      "ok": ok, "commentaire": commentaire})
    print(f"  [{'OK  ' if ok else 'ECART'}] {nom} — attendu {attendu}, obtenu {obtenu}"
          + (f"  ({commentaire})" if commentaire else ""))


def pousser(H, bus_id, lat, lng, vitesse=40.0):
    return requests.post(f"{GW}/api/gps/position", headers=H, timeout=20, json={
        "cibleType": "BUS", "cibleId": bus_id, "latitude": lat, "longitude": lng,
        "vitesse": vitesse, "cap": 90.0, "precision": 5.0}).status_code


def live(types=None, limit=200):
    d = requests.get(f"{MS11}/api/analytique/live?limit={limit}", timeout=20).json()
    an = d.get("anomalies", [])
    return [a for a in an if (types is None or a.get("type") in types)], d.get("seuils", {})


def main() -> int:
    print("\n=== Recette Phase 5 — chaîne temps réel ===\n")
    TA = requests.post(f"{GW}/api/auth/login",
                       json={"email": "admin@transport.ma", "motDePasse": "Admin123!"},
                       timeout=15).json()["token"]
    H = {"Authorization": f"Bearer {TA}"}

    # ── choix d'un bus doté d'un groupe et d'élèves ──
    eleves = requests.get("http://localhost:8082/internal/eleves", timeout=30).json()
    par_bus: dict[int, set] = {}
    for e in eleves:
        if e.get("busId") and e.get("groupeId"):
            par_bus.setdefault(e["busId"], set()).add(e["groupeId"])
    bus_id = next(iter(par_bus))
    groupe_id = next(iter(par_bus[bus_id]))
    print(f"Bus {bus_id} · groupe {groupe_id} · {sum(1 for e in eleves if e.get('busId') == bus_id)} élèves\n")

    # Le cycle de trajet appartient au CHAUFFEUR du bus : `demarrer` et `terminer`
    # sont ouverts à ADMIN par RBAC, mais le service vérifie ensuite la propriété
    # (voir TR-0). On utilise donc le jeton du chauffeur pour ces trois appels.
    import csv
    with (RACINE / "comptes_utilisateurs.csv").open(encoding="utf-8-sig") as f:
        lignes = [l for l in csv.DictReader(f) if l["role"] == "CHAUFFEUR"]
    ch_id = requests.get(f"http://localhost:8081/api/bus/{bus_id}/chauffeur", timeout=20).json()
    ch_id = ch_id.get("chauffeurId", ch_id) if isinstance(ch_id, dict) else ch_id
    ligne = next(l for l in lignes if int(l["userId"]) == int(ch_id))
    tc = requests.post(f"{GW}/api/auth/login",
                       json={"email": ligne["email"], "motDePasse": ligne["motDePasse"]},
                       timeout=15).json()
    HC = {"Authorization": f"Bearer {tc['token']}"}
    print(f"Chauffeur du bus : #{ch_id} ({ligne['email']})")

    # ── 0. l'ADMIN peut-il clore un trajet ? (RBAC dit oui, le service dit non) ──
    actifs = requests.get(f"{GW}/api/trajets/actifs", headers=H, timeout=20).json()
    residuels = [t for t in actifs if t.get("busId") == bus_id]
    if residuels:
        ra = requests.post(f"{GW}/api/trajets/{residuels[0]['id']}/terminer", headers=H, timeout=30)
        note("TR-0 · Un ADMIN peut-il clore le trajet d'un chauffeur ?",
             "200 (il est autorisé par @PreAuthorize)",
             f"HTTP {ra.status_code} — {ra.text[:70]}", ra.status_code == 200,
             "si non : téléphone du chauffeur HS ⇒ bus bloqué SANS recours administratif")

    # purge, avec le jeton du chauffeur cette fois
    for _ in range(5):
        actifs = requests.get(f"{GW}/api/trajets/actifs", headers=H, timeout=20).json()
        restants = [t for t in actifs if t.get("busId") == bus_id]
        if not restants:
            break
        for t in restants:
            rc = requests.post(f"{GW}/api/trajets/{t['id']}/terminer", headers=HC, timeout=30)
            print(f"  (purge : trajet #{t['id']} → HTTP {rc.status_code})")
        time.sleep(1.5)

    # ── 1. tournée MS5 puis démarrage AVEC géométrie ──
    print("── Cycle de trajet ──")
    t = requests.post(f"{GW}/api/planification/tournee?groupeId={groupe_id}&sens=matin",
                      headers=H, timeout=180).json()
    geo = t.get("geometrie") or []
    note("TR-1 · MS5 fournit une géométrie exploitable",
         "> 100 points", f"{len(geo)} points, {t.get('distance_m')} m, {t.get('duree_min')} min",
         len(geo) > 100)

    r = requests.post(f"{GW}/api/trajets/demarrer", headers=HC, timeout=60, json={
        "busId": bus_id, "sens": "MATIN", "groupeId": groupe_id, "geometrie": geo,
        "distancePlanM": t.get("distance_m"), "dureePlanMin": t.get("duree_min")})
    note("TR-2 · Démarrage du trajet AVEC géométrie", "201/200", r.status_code,
         r.status_code in (200, 201), "sans géométrie, MS11 est désarmé EN SILENCE (piège 12)")
    trajet_id = r.json().get("id") if r.status_code in (200, 201) else None

    # ── 2. non-idempotence : un second démarrage doit être REFUSÉ ──
    r2 = requests.post(f"{GW}/api/trajets/demarrer", headers=HC, timeout=60, json={
        "busId": bus_id, "sens": "MATIN", "groupeId": groupe_id, "geometrie": geo})
    note("TR-3 · Second démarrage du même bus refusé (non-idempotence)",
         400, r2.status_code, r2.status_code == 400,
         "c'est le cas que la file hors ligne de chauffeur-mobile réconcilie via /mon-actif")

    # ── 3. la route figée est bien exposée (référence de surveillance MS11) ──
    rr = requests.get(f"{GW}/api/trajets/bus/{bus_id}/route", headers=H, timeout=30)
    rj = rr.json() if rr.status_code == 200 else {}
    pts = rj.get("geometrie") or []
    note("TR-4 · GET /trajets/bus/{id}/route — polyligne ET totaux figés",
         "polyligne + distance + durée",
         f"HTTP {rr.status_code}, {len(pts)} pts, {rj.get('distancePlanM')} m, {rj.get('dureePlanMin')} min",
         rr.status_code == 200 and len(pts) > 100,
         "séparé de /actif : la géométrie pèse des dizaines de Ko, /actif est sondé toutes les 15 s")

    time.sleep(2)

    # ── 4. VITESSE_EXCESSIVE ──
    print("\n── Règles live MS11 ──")
    _, seuils = live()
    lat0, lng0 = geo[len(geo) // 3]
    avant_v, _ = live({"VITESSE_EXCESSIVE"})
    pousser(H, bus_id, lat0, lng0, vitesse=seuils.get("vitesse_kmh", 90) + 25)
    time.sleep(4)
    apres_v, _ = live({"VITESSE_EXCESSIVE"})
    note("TR-5 · VITESSE_EXCESSIVE détectée", "nouvelle anomalie",
         f"{len(apres_v) - len(avant_v)} nouvelle(s) (seuil {seuils.get('vitesse_kmh')} km/h)",
         len(apres_v) > len(avant_v))

    # ── 5. DEVIATION_ITINERAIRE : la règle qui exige la route figée ──
    seuil_dev = seuils.get("deviation_m", 250)
    pings_dev = int(seuils.get("deviation_pings", 2))
    avant_d, _ = live({"DEVIATION_ITINERAIRE"})

    # on suit la tournée quelques points, puis on s'en écarte franchement
    for lat, lng in geo[len(geo) // 3: len(geo) // 3 + 3]:
        pousser(H, bus_id, lat, lng)
        time.sleep(0.5)
    # ~900 m au nord-est de la polyligne : au-delà du seuil même en repassant
    # près d'un autre tronçon de la tournée (le cycle fermé du piège n° 17)
    dlat, dlng = 0.0081, 0.0097
    for _ in range(pings_dev + 3):
        pousser(H, bus_id, lat0 + dlat, lng0 + dlng)
        time.sleep(0.9)
    time.sleep(4)
    apres_d, _ = live({"DEVIATION_ITINERAIRE"})
    nouvelles = [a for a in apres_d if a not in avant_d]
    ecart = max((a.get("ecart_m") or 0) for a in nouvelles) if nouvelles else 0
    note("TR-6 · DEVIATION_ITINERAIRE détectée (surveillance MS11 armée)",
         f"écart > {seuil_dev} m", f"{len(nouvelles)} anomalie(s), écart max {ecart} m "
         f"(anti-rebond {pings_dev} pings)",
         len(apres_d) > len(avant_d),
         "prouve que MS1 a bien transmis la géométrie à MS11 au démarrage")

    # ── 6. incident MS10 → MS4 ──
    print("\n── Incident MS10 → RabbitMQ → MS4 ──")
    ri = requests.post(f"{GW}/api/incidents", headers=H, timeout=20, json={
        "busId": bus_id, "type": "PANNE", "description": "Recette finale — incident de test"})
    note("TR-7 · Signalement d'incident", "201/200", ri.status_code, ri.status_code in (200, 201))
    inc_id = ri.json().get("id") if ri.status_code in (200, 201) else None
    time.sleep(3)
    if inc_id:
        rs = requests.patch(f"{GW}/api/incidents/{inc_id}/statut", headers=H, timeout=20,
                            json={"statut": "RESOLU"})
        note("TR-8 · Résolution → publication incident.resolu", 200, rs.status_code,
             rs.status_code == 200)
        time.sleep(3)
        n = requests.get(f"{GW}/api/notifications?page=0&size=50&tri=dateEnvoi&sens=desc",
                         headers=H, timeout=30).json()
        lst = n if isinstance(n, list) else n.get("content", [])
        types = {x.get("type") for x in lst[:50]}
        note("TR-9 · MS4 a produit des notifications d'incident",
             "INCIDENT_SIGNALE / INCIDENT_RESOLU",
             ", ".join(sorted(t for t in types if t and "INCIDENT" in t)) or "aucune",
             any(t and "INCIDENT" in t for t in types))
        requests.delete(f"{GW}/api/incidents/{inc_id}", headers=H, timeout=20)

    # ── 7. fin du trajet ──
    if trajet_id:
        rf = requests.post(f"{GW}/api/trajets/{trajet_id}/terminer", headers=HC, timeout=30)
        note("TR-10 · Fin du trajet (purge de la route de référence MS11)",
             200, rf.status_code, rf.status_code == 200)

    # ── 8. dette RabbitMQ : les files sans consommateur ──
    print("\n── Dette RabbitMQ ──")
    try:
        qs = requests.get(RABBIT, auth=("admin", "admin123"), timeout=20).json()
        orphelines = {q["name"]: q.get("messages", 0) for q in qs
                      if q.get("consumers", 0) == 0 and not q["name"].startswith("amq")}
        total = sum(orphelines.values())
        note("TR-11 · Files déclarées SANS consommateur (croissance non bornée)",
             "0 message accumulé", f"{len(orphelines)} files, {total} messages",
             total == 0,
             " · ".join(f"{k}={v}" for k, v in sorted(orphelines.items(), key=lambda x: -x[1])[:4]))
        sans_conso = [q["name"] for q in qs
                      if q.get("consumers", 0) == 0 and not q["name"].startswith("amq")]
        actives = [q["name"] for q in qs if q.get("consumers", 0) > 0]
        note("TR-12 · Toutes les files fonctionnelles ont un consommateur",
             "aucune file métier orpheline", f"{len(actives)} files consommées",
             all(not n.startswith(("ms4.", "ms6.", "ms11.", "ms12.")) for n in sans_conso))
    except Exception as e:
        note("TR-11 · Files RabbitMQ", "lisible", f"erreur : {e}", False)

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({"date": time.strftime("%Y-%m-%d %H:%M:%S"),
                                  "total": len(resultats), "ecarts": _ecarts,
                                  "assertions": resultats}, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(f"\n=== {len(resultats) - _ecarts}/{len(resultats)} conformes · {_ecarts} écart(s) ===")
    return 0 if _ecarts == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
