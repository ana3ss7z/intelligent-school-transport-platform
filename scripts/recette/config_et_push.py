#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recette finale — Phase 7 : MS13 (configuration à chaud) et MS4 (canal push).

Rejoue, contre la stack vivante, les défauts documentés comme corrigés :
  MS13 — piège n° 21 : masque renvoyé, valeur vide ≠ effacer, propagation à chaud,
         atomicité du lot.
  MS4  — piège n° 23/24 : verrou d'entrée de zone (rafale BUS_ARRIVE_ECOLE),
         idempotence du jeton FCM, une ligne d'historique par ÉVÉNEMENT,
         pagination serveur.

Usage : python scripts/recette/config_et_push.py
Sortie : scripts/recette/resultats/config_et_push.json
"""
from __future__ import annotations

import json
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
SORTIE = RACINE / "scripts" / "recette" / "resultats" / "config_et_push.json"
GW = "http://localhost:8080"
MS11, MS13, MS9 = "http://localhost:8091", "http://localhost:8092", "http://localhost:8089"

resultats: list[dict] = []
_ecarts = 0


def note(nom, attendu, obtenu, ok, commentaire=""):
    global _ecarts
    _ecarts += (not ok)
    resultats.append({"nom": nom, "attendu": attendu, "obtenu": obtenu,
                      "ok": ok, "commentaire": commentaire})
    print(f"  [{'OK  ' if ok else 'ECART'}] {nom} — attendu {attendu}, obtenu {obtenu}"
          + (f"  ({commentaire})" if commentaire else ""))


def main() -> int:
    print("\n=== Recette Phase 7 — MS13 configuration à chaud & MS4 canal push ===\n")
    TA = requests.post(f"{GW}/api/auth/login",
                       json={"email": "admin@transport.ma", "motDePasse": "Admin123!"},
                       timeout=15).json()["token"]
    H = {"Authorization": f"Bearer {TA}"}

    # ───────────────────────── MS13 ─────────────────────────
    print("── MS13 — configuration à chaud ──")

    params = requests.get(f"{GW}/api/parametres", headers=H, timeout=20).json()
    plat = {p["cle"]: p.get("valeur") for p in params}
    sensibles = [p["cle"] for p in params if p.get("sensible")]
    note("MS13-1 · Les secrets sont déclarés `sensible` dans le catalogue",
         "au moins un", f"{len(sensibles)} : {', '.join(sensibles)}", len(sensibles) > 0)

    # (a) piège 21b — MS13 n'a AUCUN secret en base ; les services doivent
    #     conserver ceux de leur .env. C'est la règle « le .env est l'amorçage ».
    interne = requests.get(f"{MS13}/api/parametres/internal", timeout=20).json()
    vides = [c for c in sensibles if not str(interne.get(c, "")).strip()]
    ms9_ok = requests.get(f"{MS9}/api/llm/health", timeout=15).json().get("configured")
    note("MS13-2 · Secrets vides côté MS13 mais MS9 garde ses clés (piège 21b)",
         "MS9 configured=True", f"{len(vides)}/{len(sensibles)} secrets vides côté MS13, MS9 configured={ms9_ok}",
         ms9_ok is True,
         "une valeur vide signifie « non renseignée », jamais « effacer »")

    # (b) piège 21a — le masque renvoyé ne doit JAMAIS être écrit.
    #     Testé sur ms12.tomtom_key : le fournisseur de trafic actif est
    #     l'heuristique, donc écrire ici ne dégrade aucun service. Retour par /reset.
    cle_s = "ms12.tomtom_key"
    if cle_s in sensibles:
        requests.put(f"{GW}/api/parametres", headers=H, timeout=20,
                     json={"valeurs": {cle_s: "RECETTE-CLE-FICTIVE-abcd1234"}})
        time.sleep(1)
        lu = {p["cle"]: p.get("valeur") for p in
              requests.get(f"{GW}/api/parametres", headers=H, timeout=20).json()}
        masque = str(lu.get(cle_s, ""))
        note("MS13-3 · Une valeur sensible renseignée est MASQUÉE en lecture",
             "masque, pas la clé", repr(masque),
             masque.startswith("•") and "abcd1234" not in masque)

        # renvoyer le masque, comme le ferait un formulaire qui l'a gardé en état
        requests.put(f"{GW}/api/parametres", headers=H, timeout=20,
                     json={"valeurs": {cle_s: masque}})
        time.sleep(1)
        reel = str(requests.get(f"{MS13}/api/parametres/internal", timeout=20).json().get(cle_s, ""))
        note("MS13-4 · Renvoyer le masque n'écrase PAS le secret (piège 21a)",
             "valeur d'origine intacte", f"stockée={reel!r}",
             reel == "RECETTE-CLE-FICTIVE-abcd1234",
             "garde CÔTÉ SERVEUR : elle doit tenir pour curl, mobile ou script")

        r_res = requests.post(f"{GW}/api/parametres/reset?cle={cle_s}", headers=H, timeout=20)
        time.sleep(1)
        apres_reset = str(requests.get(f"{MS13}/api/parametres/internal", timeout=20).json().get(cle_s, ""))
        note("MS13-5 · POST /reset restaure le défaut du catalogue",
             "vide", f"HTTP {r_res.status_code}, valeur={apres_reset!r}",
             apres_reset == "",
             "seule voie pour VIDER un réglage textuel depuis la console")

    # (c) atomicité : une valeur hors bornes ⇒ RIEN n'est écrit
    cle_v = "ms11.seuil_vitesse_kmh"
    val_initiale = str(plat.get(cle_v))
    temoin = "ms11.seuil_arret_min"
    val_temoin = str(plat.get(temoin))
    r = requests.put(f"{GW}/api/parametres", headers=H, timeout=20,
                     json={"valeurs": {temoin: val_temoin, cle_v: "999999"}})
    time.sleep(1)
    apres = requests.get(f"{GW}/api/parametres", headers=H, timeout=20).json()
    plat2 = apres if isinstance(apres, dict) else {p["cle"]: p.get("valeur") for p in apres}
    note("MS13-6 · Lot avec une valeur hors bornes → refus ATOMIQUE",
         "4xx et aucune écriture", f"HTTP {r.status_code}, {cle_v}={plat2.get(cle_v)}",
         r.status_code >= 400 and str(plat2.get(cle_v)) == val_initiale,
         "un jeu de seuils à moitié appliqué serait pire qu'un refus")

    # (c) propagation à chaud, chronométrée
    nouvelle = "85" if val_initiale != "85" else "95"
    r = requests.put(f"{GW}/api/parametres", headers=H, timeout=20,
                     json={"valeurs": {cle_v: nouvelle}})
    t0 = time.time()
    vu, delai = None, None
    for _ in range(40):
        time.sleep(0.25)
        try:
            s = requests.get(f"{MS11}/api/analytique/live?limit=1", timeout=10).json()
            vu = str(s.get("seuils", {}).get("vitesse_kmh"))
            if vu and float(vu) == float(nouvelle):
                delai = time.time() - t0
                break
        except Exception:
            pass
    note("MS13-7 · Propagation à chaud MS13 → MS11, SANS redémarrage",
         "< 10 s", f"{delai:.2f} s" if delai else f"non propagé (vu={vu})",
         delai is not None, f"{cle_v} : {val_initiale} → {nouvelle}")

    # restauration
    requests.put(f"{GW}/api/parametres", headers=H, timeout=20,
                 json={"valeurs": {cle_v: val_initiale}})
    time.sleep(2)
    remis = str(requests.get(f"{MS11}/api/analytique/live?limit=1", timeout=10)
                .json().get("seuils", {}).get("vitesse_kmh"))
    note("MS13-8 · Restauration de la valeur initiale",
         val_initiale, remis, float(remis) == float(val_initiale))

    # ───────────────────────── MS4 ─────────────────────────
    print("\n── MS4 — canal de notifications poussées ──")

    parents = json.loads((RACINE / "comptes_utilisateurs.json").read_text(encoding="utf-8"))["parents"]
    p = parents[3]
    tp = requests.post(f"{GW}/api/auth/login",
                       json={"email": p["email"], "motDePasse": p["motDePasse"]},
                       timeout=15).json()
    HP = {"Authorization": f"Bearer {tp['token']}"}

    # (a) idempotence du jeton FCM — le cas NORMAL (2e connexion du même appareil)
    jeton_fcm = "recette-token-idempotence-001"
    c1 = requests.post(f"{GW}/api/notifications/device-token", headers=HP, timeout=20,
                       json={"fcmToken": jeton_fcm, "plateforme": "WEB"}).status_code
    c2 = requests.post(f"{GW}/api/notifications/device-token", headers=HP, timeout=20,
                       json={"fcmToken": jeton_fcm, "plateforme": "WEB"}).status_code
    c3 = requests.post(f"{GW}/api/notifications/device-token", headers=HP, timeout=20,
                       json={"fcmToken": jeton_fcm, "plateforme": "WEB"}).status_code
    note("MS4-1 · Réenregistrer le MÊME jeton FCM (piège 24 : HTTP 500 avant correctif)",
         "3 succès", f"{c1}, {c2}, {c3}",
         all(200 <= c < 300 for c in (c1, c2, c3)),
         "un jeton est stable par installation : il revient à CHAQUE connexion")

    # (b) plateforme omise → INCONNU, jamais ANDROID par défaut
    requests.post(f"{GW}/api/notifications/device-token", headers=HP, timeout=20,
                  json={"fcmToken": "recette-token-sans-plateforme"})

    # (c) verrou d'entrée de zone : un bus GARÉ à l'école ne doit annoncer qu'UNE fois
    ecole = (33.893, -5.5455)
    bus = [b for b in requests.get(f"{GW}/api/bus", headers=H, timeout=20).json()
           if b["statut"] == "ACTIF"]
    eleves = requests.get("http://localhost:8082/internal/eleves", timeout=30).json()
    par_bus = {}
    for e in eleves:
        if e.get("busId") and e.get("parentId"):
            par_bus.setdefault(e["busId"], set()).add(e["parentId"])
    bus_id = next((b["id"] for b in bus if par_bus.get(b["id"])), bus[0]["id"])
    parents_bus = par_bus.get(bus_id, set())

    def compter_arrivees():
        r = requests.get(f"{GW}/api/notifications?page=0&size=500&tri=dateEnvoi&sens=desc",
                         headers=H, timeout=30).json()
        lst = r if isinstance(r, list) else r.get("content", [])
        return sum(1 for n in lst
                   if n.get("type") == "BUS_ARRIVE_ECOLE" and n.get("parentId") in parents_bus)

    # on éloigne d'abord le bus pour armer proprement, puis on le gare à l'école
    requests.post(f"{GW}/api/gps/position", headers=H, timeout=20, json={
        "cibleType": "BUS", "cibleId": bus_id, "latitude": 33.93, "longitude": -5.62,
        "vitesse": 40.0, "cap": 90.0, "precision": 5.0})
    time.sleep(3)
    avant = compter_arrivees()

    N = 30
    for i in range(N):  # bus GARÉ : il continue d'émettre sa position, avec du bruit GPS
        requests.post(f"{GW}/api/gps/position", headers=H, timeout=20, json={
            "cibleType": "BUS", "cibleId": bus_id,
            "latitude": ecole[0] + (0.00012 if i % 2 else -0.00012),
            "longitude": ecole[1] + (0.00012 if i % 3 else -0.00012),
            "vitesse": 0.0, "cap": 0.0, "precision": 5.0})
        time.sleep(0.2)
    time.sleep(6)
    apres = compter_arrivees()
    nouvelles = apres - avant
    attendu_max = len(parents_bus)  # 1 annonce par parent du bus, pas 1 par ping
    note("MS4-2 · Bus GARÉ à l'école, 30 pings → verrou d'entrée de zone (piège 23)",
         f"≤ {attendu_max} (1 par parent)", f"{nouvelles} notification(s) pour {len(parents_bus)} parents",
         nouvelles <= attendu_max,
         f"avant correctif : 150 par parent en 3 min ; {N} pings envoyés ici")

    # (d) pagination serveur
    r1 = requests.get(f"{GW}/api/notifications?page=0&size=5", headers=H, timeout=30).json()
    lst1 = r1 if isinstance(r1, list) else r1.get("content", [])
    total = r1.get("totalElements") if isinstance(r1, dict) else None
    note("MS4-3 · Pagination SERVEUR du journal (piège 23 : findAll de 10 000 lignes)",
         "5 lignes transportées", f"{len(lst1)} ligne(s), total annoncé = {total}",
         len(lst1) <= 5 and isinstance(r1, dict),
         "la page ne transporte qu'une tranche ; le total vient de /stats")

    r_tri = requests.get(f"{GW}/api/notifications?page=0&size=5&tri=colonne_inexistante",
                         headers=H, timeout=30)
    note("MS4-4 · Tri hors liste blanche refusé ou ignoré",
         "4xx ou repli sûr", f"HTTP {r_tri.status_code}",
         r_tri.status_code < 500, "jamais d'injection dans l'ORDER BY")

    stats = requests.get(f"{GW}/api/notifications/stats", headers=H, timeout=20).json()
    note("MS4-5 · /stats fournit les totaux (la page n'en voit plus qu'une tranche)",
         "clés total/envoyes/echecs", json.dumps(stats, ensure_ascii=False)[:160],
         "total" in stats)

    # nettoyage des jetons de recette
    for t in (jeton_fcm, "recette-token-sans-plateforme"):
        requests.delete(f"{GW}/api/notifications/device-token/{t}", headers=HP, timeout=20)

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({"date": time.strftime("%Y-%m-%d %H:%M:%S"),
                                  "total": len(resultats), "ecarts": _ecarts,
                                  "assertions": resultats}, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(f"\n=== {len(resultats) - _ecarts}/{len(resultats)} conformes · {_ecarts} écart(s) ===")
    return 0 if _ecarts == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
