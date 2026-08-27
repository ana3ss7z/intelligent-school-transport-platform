#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recette — les 5 briques IA : les résultats sont-ils JUSTES ?

Ce script ne vérifie pas que les services répondent — `contrats.py` le fait déjà. Il vérifie
que ce qu'ils répondent est **correct** : contraintes métier respectées, grandeurs cohérentes
entre elles, propriétés que les modèles sont censés garantir, et déterminisme.

  MS6  regroupement     — capacité, exhaustivité, k, silhouette, déterminisme
  MS5  tournées         — permutation valide, convergence distance/géométrie, gain, sens soir
  MS12 prédiction ETA   — garde anti-extrapolation, monotonie, effet du contexte, intervalle
  MS11 anomalies        — métriques gelées, seuils publiés, détection réelle d'une injection
  MS9  assistant        — cascade réellement servie, NL2SQL exact

Usage : python scripts/recette/ia.py
Sortie : scripts/recette/resultats/ia.json
Exit   : 0 si aucun écart, 2 sinon.
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
import time
from collections import Counter

import requests

for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RACINE = pathlib.Path(__file__).resolve().parents[2]
SORTIE = RACINE / "scripts" / "recette" / "resultats" / "ia.json"
GW = "http://localhost:8080"
MS2_INT = "http://localhost:8082/internal/eleves"
MS6, MS11, MS12 = "http://localhost:8086", "http://localhost:8091", "http://localhost:8088"
ECOLE = (33.893, -5.5455)

resultats: list[dict] = []
_ecarts = 0


def note(brique, nom, attendu, obtenu, ok, commentaire=""):
    global _ecarts
    _ecarts += (not ok)
    resultats.append({"brique": brique, "nom": nom, "attendu": attendu,
                      "obtenu": obtenu, "ok": ok, "commentaire": commentaire})
    print(f"  [{'OK  ' if ok else 'ECART'}] {nom}\n"
          f"          attendu {attendu} · obtenu {obtenu}"
          + (f"\n          {commentaire}" if commentaire else ""))


def hav(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    return 2 * R * math.asin(math.sqrt(
        math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))


def jeton_admin():
    return requests.post(f"{GW}/api/auth/login",
                         json={"email": "admin@transport.ma", "motDePasse": "Admin123!"},
                         timeout=25).json()["token"]


# ═══════════════════════════ MS6 — REGROUPEMENT ═══════════════════════════
def ms6(H):
    print("\n── MS6 · Regroupement capacitaire ──")
    cfg = json.loads((RACINE / "ms6-clustering/notebooks/production_config.json")
                     .read_text(encoding="utf-8"))
    capacite = cfg["capacite_bus"]
    k_gele = cfg["k_production"]

    eleves = requests.get(MS2_INT, timeout=40).json()
    grp = Counter(e.get("groupeId") for e in eleves)
    tailles = {g: n for g, n in grp.items() if g not in (None, 999)}

    note("MS6", "Contrainte DURE : aucun groupe ne dépasse la capacité du bus",
         f"toutes les tailles ≤ {capacite}",
         f"max = {max(tailles.values())} (groupe {max(tailles, key=tailles.get)})",
         max(tailles.values()) <= capacite,
         "c'est la seule contrainte que l'algorithme garantit par construction")

    orphelins = [e["id"] for e in eleves if e.get("groupeId") is None]
    note("MS6", "Exhaustivité : chaque élève a un groupe",
         "0 élève sans groupe", f"{len(orphelins)} orphelin(s)", not orphelins)

    sans_bus = [e["id"] for e in eleves if e.get("groupeId") not in (None, 999) and not e.get("busId")]
    note("MS6", "Liaison groupe↔bus : chaque élève groupé a un bus",
         "0 élève sans bus", f"{len(sans_bus)} sans bus", not sans_bus,
         "sans busId, MS4 ne trouve aucun parent à notifier")

    note("MS6", "Nombre de bus conforme à la configuration gelée",
         f"k = {k_gele}", f"k = {len(tailles)}", len(tailles) == k_gele)

    k_min = math.ceil(len(eleves) / capacite)
    note("MS6", "Le nombre de bus est réalisable pour l'effectif",
         f"k ≥ ⌈{len(eleves)}/{capacite}⌉ = {k_min}", f"k = {len(tailles)}",
         len(tailles) >= k_min)

    # Le verdict n'existe qu'après un calcul : au démarrage du service il est nul. On lance
    # donc d'abord la relance (qui sert aussi au test de déterminisme), puis on le lit.
    print("     … relance du calcul pour vérifier le déterminisme")
    avant = {e["id"]: e.get("busId") for e in eleves}
    requests.post(f"{GW}/api/clustering/production?appliquer=true", headers=H, timeout=300)
    time.sleep(2)

    q = requests.get(f"{MS6}/api/clustering/quality", timeout=40).json()
    dv = q.get("dernier_verdict") or {}
    mes = dv.get("mesures", {})
    note("MS6", "Verdict du garde-fou qualité",
         "OK", f"{dv.get('niveau')} · silhouette {mes.get('silhouette')}",
         dv.get("niveau") == "OK", " · ".join(dv.get("raisons", [])) or "aucune réserve")

    plancher = q.get("seuils", {}).get("sil_floor_rel", 0.75) * 0.4256
    sil = mes.get("silhouette")
    note("MS6", "Silhouette au-dessus du plancher d'effondrement",
         f"≥ {plancher:.4f}", sil, sil is not None and sil >= plancher,
         "le plancher vaut 0,75 × le point de conception, pas un seuil générique de 0,5")

    apres = {e["id"]: e.get("busId") for e in requests.get(MS2_INT, timeout=40).json()}
    chg = [i for i in set(avant) & set(apres) if avant[i] != apres[i]]
    note("MS6", "Déterminisme : relancer le calcul ne déplace personne",
         "0 élève déplacé", f"{len(chg)} déplacé(s)", not chg,
         "un algorithme qui rebat les cartes à chaque exécution serait inexploitable")

    d = requests.get(f"{MS6}/api/clustering/diagnostics", timeout=60).json()
    note("MS6", "Diagnostics cohérents avec la base",
         f"{len(eleves)} élèves", f"{d.get('n_eleves')} élèves",
         d.get("n_eleves") == len(eleves))
    return tailles


# ═══════════════════════════ MS5 — TOURNÉES ═══════════════════════════
def ms5(H, tailles):
    print("\n── MS5 · Optimisation des tournées ──")
    eleves = requests.get(MS2_INT, timeout=40).json()
    par_groupe = {}
    for e in eleves:
        if e.get("groupeId") not in (None, 999):
            par_groupe.setdefault(e["groupeId"], []).append(e)

    ecarts_conv, gains, groupes_testes = [], [], sorted(par_groupe)[:3]
    for g in groupes_testes:
        t = requests.post(f"{GW}/api/planification/tournee?groupeId={g}&sens=matin&persister=false",
                          headers=H, timeout=240).json()
        attendus = {e["id"] for e in par_groupe[g]}
        ordre = [int(x) for x in (t.get("ordre") or [])]

        note("MS5", f"Groupe {g} — la tournée est une PERMUTATION exacte des élèves",
             f"{len(attendus)} élèves, chacun une fois",
             f"{len(ordre)} arrêts, {len(set(ordre))} distincts",
             set(ordre) == attendus and len(ordre) == len(set(ordre)),
             "un élève oublié ou compté deux fois passerait inaperçu sans ce contrôle")

        geo = t.get("geometrie") or []
        mesure = sum(hav(geo[i], geo[i + 1]) for i in range(len(geo) - 1)) if len(geo) > 1 else 0
        annonce = t.get("distance_m") or 0
        ecart = 100 * abs(mesure - annonce) / annonce if annonce else 999
        ecarts_conv.append(ecart)
        note("MS5", f"Groupe {g} — la distance annoncée décrit bien le trajet dessiné",
             "écart < 0,5 %", f"{ecart:.2f} % ({annonce:.0f} m annoncés, {mesure:.0f} m mesurés)",
             ecart < 0.5,
             "avant le correctif du 22/08 l'écart était de 10,9 % : deux trajets différents")

        vitesse = (annonce / 1000) / ((t.get("duree_min") or 1) / 60)
        note("MS5", f"Groupe {g} — vitesse moyenne plausible en ville",
             "entre 10 et 60 km/h", f"{vitesse:.1f} km/h", 10 <= vitesse <= 60)

        gains.append(t.get("gain_vs_baseline_%", 0))

    note("MS5", "Gain vs l'ordre naïf, sur les groupes testés",
         "≥ 0 % partout", f"{[round(x, 1) for x in gains]} %", all(g >= 0 for g in gains),
         f"moyenne {sum(gains)/len(gains):.1f} %")

    # décision de conception : le soir reprend le MÊME ordre que le matin
    g = groupes_testes[0]
    m = requests.post(f"{GW}/api/planification/tournee?groupeId={g}&sens=matin&persister=false",
                      headers=H, timeout=240).json()
    s = requests.post(f"{GW}/api/planification/tournee?groupeId={g}&sens=soir&persister=false",
                      headers=H, timeout=240).json()
    note("MS5", "Le soir reprend le MÊME ordre que le matin (choix de conception)",
         "ordres identiques",
         "identiques" if m.get("ordre") == s.get("ordre") else "différents",
         m.get("ordre") == s.get("ordre"),
         "garder le même ordre équilibre le temps à bord sur la journée (verify_sens.py)")


# ═══════════════════════════ MS12 — PRÉDICTION ETA ═══════════════════════════
def ms12(H):
    print("\n── MS12 · Prédiction du temps d'arrivée ──")
    info = requests.get(f"{MS12}/api/eta/model-info", timeout=30).json()
    cfg = json.loads((RACINE / "ms12-prediction/data/eta_config.json").read_text(encoding="utf-8"))
    note("MS12", "Le modèle servi est bien celui qui a été gelé",
         cfg.get("algorithme"), info.get("algorithme") or info.get("modele"),
         (info.get("algorithme") or info.get("modele")) == cfg.get("algorithme"))

    def predire(lat, lng, **extra):
        c = {"bus_lat": lat, "bus_lng": lng, "dest_lat": ECOLE[0], "dest_lng": ECOLE[1]}
        c.update(extra)
        return requests.post(f"{GW}/api/eta/predict", headers=H, timeout=120, json=c).json()

    # garde anti-extrapolation : au-delà du domaine d'entraînement, on n'extrapole pas
    proche = predire(33.8985, -5.5605)
    loin = predire(33.925, -5.62)
    note("MS12", "Garde anti-extrapolation : le mode bascule hors du domaine appris",
         "modele_direct près / facteur_contexte loin",
         f"{proche['distance_routiere_m']:.0f} m → {proche.get('mode_eta')} | "
         f"{loin['distance_routiere_m']:.0f} m → {loin.get('mode_eta')}",
         proche.get("mode_eta") == "modele_direct" and loin.get("mode_eta") == "facteur_contexte",
         "le modèle a appris sur des tronçons de 0,7 à 4 km ; au-delà il ne doit pas extrapoler")

    # monotonie : plus c'est loin, plus c'est long
    trio = [predire(*p) for p in ((33.8985, -5.5605), (33.907, -5.585), (33.925, -5.62))]
    d = [t["distance_routiere_m"] for t in trio]
    e = [t["eta_minutes"] for t in trio]
    note("MS12", "Monotonie : une distance plus grande donne une durée plus grande",
         "durées croissantes",
         " · ".join(f"{x:.0f} m → {y:.2f} min" for x, y in zip(d, e)),
         e == sorted(e) and d == sorted(d))

    note("MS12", "L'intervalle de confiance encadre bien la prédiction",
         "borne basse ≤ ETA ≤ borne haute",
         f"{proche['intervalle_min']} autour de {proche['eta_minutes']}",
         proche["intervalle_min"][0] <= proche["eta_minutes"] <= proche["intervalle_min"][1])

    # effet du contexte, à distance identique
    beau = predire(33.907, -5.585, meteo="ensoleille", trafic="fluide",
                   travaux_prevus=0, auto_context=False)
    sale = predire(33.907, -5.585, meteo="pluie", trafic="embouteillage",
                   travaux_prevus=1, auto_context=False)
    ratio = sale["eta_minutes"] / beau["eta_minutes"] if beau["eta_minutes"] else 0
    note("MS12", "Le contexte a un effet mesurable, à distance identique",
         "pluie+embouteillage nettement plus lent",
         f"beau/fluide {beau['eta_minutes']} min → pluie/embouteillage {sale['eta_minutes']} min "
         f"(×{ratio:.2f})",
         ratio > 1.3,
         "même tronçon, seul le contexte change — c'est ce que le modèle est censé capter")

    note("MS12", "La réponse déclare ses sources",
         "distance/durée = OSRM", str(proche.get("sources", {}).get("distance/duree")),
         proche.get("sources", {}).get("distance/duree") == "OSRM")


# ═══════════════════════════ MS11 — ANOMALIES ═══════════════════════════
def ms11(H):
    print("\n── MS11 · Détection d'anomalies ──")
    info = requests.get(f"{MS11}/api/analytique/model-info", timeout=30).json()
    cfg = json.loads((RACINE / "ms11-analytique/data/anomaly_config.json").read_text(encoding="utf-8"))
    note("MS11", "Le détecteur servi est celui qui a été gelé",
         cfg.get("detecteur"), info.get("detecteur"),
         info.get("detecteur") == cfg.get("detecteur"))

    m = info.get("metrics_test", {})
    gele = cfg.get("metrics_test", {})
    note("MS11", "Les métriques publiées sont celles du benchmark",
         f"PR-AUC {gele.get('PR_AUC')} · rappel {gele.get('rappel')}",
         f"PR-AUC {m.get('PR_AUC')} · rappel {m.get('rappel')}",
         m.get("PR_AUC") == gele.get("PR_AUC"))

    scan = requests.get(f"{GW}/api/analytique/anomalies/scan?limit=20", headers=H, timeout=180).json()
    p, r = scan.get("precision"), scan.get("rappel")
    note("MS11", "Le scan retrouve les incidents réels du jeu de données",
         "précision et rappel ≥ 0,5", f"précision {p} · rappel {r}",
         (p or 0) >= 0.5 and (r or 0) >= 0.5,
         "évalué contre le label incident, jamais utilisé pour l'apprentissage")

    live = requests.get(f"{MS11}/api/analytique/live?limit=5", timeout=30).json()
    seuils = live.get("seuils", {})
    note("MS11", "Les seuils de surveillance sont publiés et exploitables",
         "vitesse, arrêt, déviation présents",
         f"vitesse {seuils.get('vitesse_kmh')} km/h · arrêt {seuils.get('arret_min')} min "
         f"· déviation {seuils.get('deviation_m')} m",
         all(seuils.get(k) for k in ("vitesse_kmh", "arret_min", "deviation_m")))

    # Détection réelle. ⚠️ MS11 impose un anti-spam de 120 s par type ET par bus
    # (`_ALERT_COOLDOWN_S`) : réutiliser un bus déjà alerté ne prouverait rien. On choisit
    # donc un bus qui n'a levé aucune alerte de vitesse récemment.
    def alertes_vitesse():
        return [a for a in requests.get(f"{MS11}/api/analytique/live?limit=200", timeout=30)
                .json().get("anomalies", []) if a.get("type") == "VITESSE_EXCESSIVE"]

    recents = {a.get("busId") for a in alertes_vitesse()[-12:]}
    actifs = [b for b in requests.get(f"{GW}/api/bus", headers=H, timeout=30).json()
              if b["statut"] == "ACTIF"]
    bus = next((b for b in actifs if b["id"] not in recents), actifs[0])
    trop_vite = seuils.get("vitesse_kmh", 90) + 30

    def pousser(v):
        requests.post(f"{GW}/api/gps/position", headers=H, timeout=30, json={
            "cibleType": "BUS", "cibleId": bus["id"], "latitude": 33.90, "longitude": -5.56,
            "vitesse": v, "cap": 90.0, "precision": 5.0})

    # Le PREMIER ping d'un bus ne fait qu'initialiser l'état du monitor et ne déclenche
    # jamais rien (`observer()` retourne tôt faute de position précédente). C'est correct —
    # une vitesse dérivée exige deux points — mais il faut amorcer avant de mesurer.
    pousser(40.0)
    time.sleep(3)

    avant = len(alertes_vitesse())
    pousser(trop_vite)
    time.sleep(6)
    apres = len(alertes_vitesse())
    note("MS11", "Une vitesse injectée au-dessus du seuil est réellement détectée",
         "une nouvelle alerte", f"{apres - avant} nouvelle(s) sur le bus {bus['id']}",
         apres > avant, f"vitesse envoyée : {trop_vite} km/h (seuil {seuils.get('vitesse_kmh')})")

    # anti-spam : deux excès rapprochés sur le même bus ne doivent donner qu'UNE alerte
    pousser(trop_vite + 10)
    time.sleep(6)
    encore = len(alertes_vitesse())
    note("MS11", "Anti-spam : un second excès dans la minute ne réalerte pas",
         "aucune alerte supplémentaire", f"{encore - apres} supplémentaire(s)",
         encore == apres,
         "une alerte par type et par bus toutes les 2 min — sinon un bus rapide noierait la console")


# ═══════════════════════════ MS9 — ASSISTANT ═══════════════════════════
def ms9(H):
    print("\n── MS9 · Assistant et NL2SQL ──")
    mc = requests.get(f"{GW}/api/llm/admin/models-check", headers=H, timeout=120).json()
    note("MS9", "Les modèles de la cascade sont réellement servis par les fournisseurs",
         "verdict OK, aucun absent",
         f"{mc.get('verdict')} · absents : {mc.get('modeles_absents')}",
         mc.get("verdict") == "OK" and not mc.get("modeles_absents"),
         "deux pannes de modèle ont déjà été subies en silence (pièges n° 7 et 21c)")

    # NL2SQL : la réponse doit être VRAIE, pas seulement bien formée
    vrai = len(requests.get(MS2_INT, timeout=40).json())
    r = requests.post(f"{GW}/api/llm/admin/query", headers=H, timeout=180,
                      json={"question": "Combien d'élèves sont inscrits au total ?"}).json()
    lignes = r.get("lignes") or []
    valeur = lignes[0][0] if lignes and lignes[0] else None
    note("MS9", "NL2SQL — le chiffre renvoyé est le VRAI chiffre de la base",
         f"{vrai} élèves", f"{valeur} (SQL : {str(r.get('sql'))[:70]})",
         valeur == vrai,
         "générer du SQL valide ne suffit pas : il doit répondre à la question posée")

    note("MS9", "NL2SQL — la requête générée est bien en lecture seule",
         "commence par SELECT ou WITH", str(r.get("sql"))[:40],
         str(r.get("sql", "")).lower().lstrip().startswith(("select", "with")))


def main() -> int:
    print("\n=== Recette — justesse des 5 briques IA ===")
    H = {"Authorization": f"Bearer {jeton_admin()}"}
    tailles = ms6(H)
    ms5(H, tailles)
    ms12(H)
    ms11(H)
    ms9(H)

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({"date": time.strftime("%Y-%m-%d %H:%M:%S"),
                                  "total": len(resultats), "ecarts": _ecarts,
                                  "assertions": resultats}, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(f"\n=== {len(resultats) - _ecarts}/{len(resultats)} conformes · {_ecarts} écart(s) ===")
    print(f"Détail : {SORTIE}")
    if _ecarts:
        print("\nÉcarts :")
        for r in resultats:
            if not r["ok"]:
                print(f"  • [{r['brique']}] {r['nom']} — obtenu {r['obtenu']}")
    return 0 if _ecarts == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
