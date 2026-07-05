"""
Générateur du dataset d'ANOMALIES de MS11 (propre au service, dans ms11-analytique/data/).

Différence essentielle avec le dataset ETA de MS12 : ici les anomalies sont **hétérogènes et
contextuelles**, pour que la détection soit un vrai problème **multivarié** (et pas un simple seuil) :

- **franc** (panne/accident/route bloquée) : durée énorme → ratio très élevé (facile, unidimensionnel).
- **contextuel** (retard) : ratio *modéré* (2–3×) MAIS par conditions **légères** (trafic fluide, beau temps)
  → un même ratio serait normal en embouteillage+pluie. Un seuil sur le ratio seul **échoue** ; un modèle
  qui regarde ratio **ET** contexte réussit.
- **surcharge** (dwell) : ratio quasi normal mais **montées/descentes anormalement élevées** → invisible
  pour un seuil sur le ratio, détectable dans l'espace multivarié.

⇒ Un seuil univarié attrape surtout les « francs » ; **Isolation Forest** (ratio + contexte + dwell) attrape
les trois → justifie le ML. `incident_type` reste un LABEL (évaluation seulement).

Usage : python dataset_anomaly.py  → écrit data/anomaly_dataset.csv
"""
from __future__ import annotations
import json
import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

from config import settings
from osrm_client import route_async  # async ; on fera un petit wrapper sync
import asyncio

# ── Référentiel géographique (copie autonome — MS11 indépendant de MS12) ──
ECOLE = {"lat": 33.893, "lng": -5.5455}
CIRCUITS = {
    1: {"traverse_oued": 1, "nb_feux": 9, "arrets": [
        (33.8935, -5.5547), (33.8978, -5.5489), (33.9012, -5.5523), (33.9067, -5.5456)]},
    2: {"traverse_oued": 0, "nb_feux": 6, "arrets": [
        (33.8876, -5.5612), (33.8901, -5.5598), (33.8845, -5.5534), (33.8712, -5.5312)]},
    3: {"traverse_oued": 1, "nb_feux": 11, "arrets": [
        (33.8756, -5.5401), (33.8834, -5.5378), (33.8956, -5.5445), (33.8923, -5.5689)]},
}

F_METEO = {"ensoleille": 1.00, "nuageux": 1.03, "pluie": 1.20, "brouillard": 1.15}
F_TRAFIC = {"fluide": 1.00, "modere": 1.15, "dense": 1.40, "embouteillage": 1.80}
CAP = 50
T_EMB = 4.0  # secondes par montée/descente


def _route_sync(o, d):
    return asyncio.run(route_async(o[0], o[1], d[0], d[1]))


def _points(circuit, moment):
    a = [tuple(x) for x in circuit["arrets"]]
    return a + [(ECOLE["lat"], ECOLE["lng"])] if moment == "matin" else [(ECOLE["lat"], ECOLE["lng"])] + a[::-1]


def _cache():
    c = {}
    for cid, circ in CIRCUITS.items():
        for moment in ("matin", "soir"):
            pts = _points(circ, moment)
            for i in range(len(pts) - 1):
                dur, dist = _route_sync(pts[i], pts[i + 1])
                c[(cid, moment, i)] = (dur, dist, len(pts) - 1)
    return c


def _meteo(rng):
    return rng.choice(list(F_METEO), p=[0.62, 0.20, 0.13, 0.05])


def _trafic(rng, heure):
    pointe = (7 <= heure <= 9) or (17 <= heure <= 19)
    return rng.choice(list(F_TRAFIC), p=[0.10, 0.25, 0.35, 0.30] if pointe else [0.55, 0.30, 0.12, 0.03])


def generer(seed: int | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed if seed is not None else settings.seed)
    cache = _cache()
    debut = date(2025, 9, 8)
    lignes = []
    d = debut
    jours = 0
    while jours < settings.n_jours:
        if d.weekday() < 5:
            jours += 1
            souk = int(d.weekday() == 2)
            ramadan = int(date(2026, 2, 18) <= d <= date(2026, 3, 19))
            for moment in ("matin", "soir"):
                heure = (7.5 if moment == "matin" else 17.5) + float(rng.normal(0, 0.25))
                meteo = _meteo(rng); trafic = _trafic(rng, heure)
                for cid, circ in CIRCUITS.items():
                    n_legs = cache[(cid, moment, 0)][2]
                    # Décide d'un incident pour ce trajet et de son type
                    inc = None
                    if rng.random() < settings.incident_rate:
                        inc = rng.choice(["franc", "contextuel", "surcharge"], p=[0.4, 0.35, 0.25])
                    leg_inc = int(rng.integers(0, n_legs)) if inc else -1
                    occ = 0.0 if moment == "matin" else CAP * float(rng.uniform(0.7, 1.0))
                    for i in range(n_legs):
                        dur_base, dist, _ = cache[(cid, moment, i)]
                        mt, met = trafic, meteo   # contexte effectif (peut être forcé par un incident contextuel)

                        # montées/descentes normales
                        if moment == "matin":
                            mont = int(rng.poisson(6)) if i < n_legs - 1 else 0; desc = 0
                            occ = min(CAP, occ + mont)
                        else:
                            mont = 0; desc = int(rng.poisson(6)) if i > 0 else 0
                            occ = max(0, occ - desc)

                        f = F_TRAFIC[mt] * F_METEO[met] * (1.25 if (ramadan and moment == "soir") else 1.0) * (1.12 if souk else 1.0)
                        inc_type = "none"

                        if inc and i == leg_inc:
                            if inc == "franc":
                                mult = f * float(rng.uniform(4.0, 12.0))
                                inc_type = rng.choice(["panne", "accident", "route_bloquee"])
                            elif inc == "contextuel":
                                mt, met = "fluide", "ensoleille"      # conditions LÉGÈRES...
                                mult = float(rng.uniform(2.2, 3.2))   # ...mais ratio élevé = anormal en contexte
                                inc_type = "retard_contextuel"
                            else:  # surcharge : dwell anormal, ratio quasi normal
                                mont = int(rng.uniform(22, 36)) if moment == "matin" else mont
                                desc = int(rng.uniform(22, 36)) if moment == "soir" else desc
                                mult = f
                                inc_type = "surcharge"
                        else:
                            mult = f

                        dwell = (mont + desc) * T_EMB
                        bruit = float(rng.normal(0, 0.08 * dur_base * mult))
                        reel_s = max(5.0, dur_base * mult + dwell + bruit)

                        lignes.append({
                            "date": d.isoformat(), "moment": moment, "heure_depart": round(heure, 3),
                            "circuit_id": cid, "leg_id": i, "meteo": met, "trafic": mt,
                            "ramadan": ramadan, "jour_souk": souk, "travaux_prevus": 0,
                            "traverse_oued": circ["traverse_oued"], "nb_feux": circ["nb_feux"],
                            "distance_routiere_m": round(dist, 1), "duree_base_s": round(dur_base, 1),
                            "nb_arrets_restants": n_legs - 1 - i, "nb_montees": mont, "nb_descentes": desc,
                            "taux_occupation": round(min(1.0, occ / CAP), 3),
                            "retard_cumule_s": 0.0,
                            "incident_type": inc_type,
                            "duree_reelle_min": round(reel_s / 60.0, 3),
                        })
        d += timedelta(days=1)

    return pd.DataFrame(lignes)


def main():
    os.makedirs(settings.data_dir, exist_ok=True)
    df = generer()
    df.to_csv(settings.dataset_path, index=False)
    ratio = (df["duree_reelle_min"] * 60 / df["duree_base_s"].clip(lower=1))
    stats = {
        "lignes": len(df),
        "part_incidents_%": round(100 * (df["incident_type"] != "none").mean(), 2),
        "types": df["incident_type"].value_counts().to_dict(),
        "ratio_normal_p95": round(float(ratio[df["incident_type"] == "none"].quantile(0.95)), 2),
        "ratio_incident_med": round(float(ratio[df["incident_type"] != "none"].median()), 2),
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print("→ écrit :", settings.dataset_path)


if __name__ == "__main__":
    main()
