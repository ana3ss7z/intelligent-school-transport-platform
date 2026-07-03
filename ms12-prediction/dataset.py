"""
Générateur du dataset ETA (~180 jours d'école) — stratégie (B) : ancré sur OSRM réel.

Approche (simple à comprendre) :
1. Base RÉELLE : durée/distance de chaque tronçon = vraies valeurs routières OSRM de Meknès
   (calculées une fois par tronçon, mises en cache ; repli vol d'oiseau si OSRM est éteint).
2. On simule ~180 jours d'école (week-ends / vacances / fériés exclus = pas de service).
3. La durée réelle d'un tronçon = base × facteurs (trafic, météo, ramadan, souk, travaux) + dwell + bruit.
   Les facteurs viennent de la littérature transport (documentés dans le notebook).
4. Cas extrêmes : ~5 % des trajets subissent un INCIDENT imprévisible (panne, accident, ...) →
   gros retard irrégulier. `incident_type` est un LABEL (pas une feature) — réutilisé en S12 (anomalies).
5. Feature historique SANS FUITE : moyenne des durées réalisées des jours PASSÉS (même circuit/moment/tronçon).

Usage : `python dataset.py`  → écrit data/eta_dataset.csv
"""
from __future__ import annotations
import json
from datetime import date

import numpy as np
import pandas as pd

from config import settings
from osrm_client import route_sync
from context.circuits import CIRCUITS, routes_circuit           # table circuits partagée (DRY)
from context.calendar_ma import jours_ecole, est_ramadan, jour_souk  # calendrier partagé

# ── Facteurs métier (sourcés — cf. notebook) ──
F_METEO = {"ensoleille": 1.00, "nuageux": 1.03, "pluie": 1.20, "brouillard": 1.15}
F_TRAFIC = {"fluide": 1.00, "modere": 1.15, "dense": 1.40, "embouteillage": 1.80}
INCIDENTS = {          # (min_retard_min, max_retard_min)
    "panne": (20, 60), "accident": (30, 90), "route_bloquee": (10, 40),
    "absence_chauffeur": (30, 120), "retard_admin": (5, 20),
}
CAPACITE_BUS = 50


def _cache_tronçons() -> dict:
    """Durée/distance OSRM par tronçon (calculées une seule fois, réutilisées sur 180 j)."""
    cache = {}
    for cid, circuit in CIRCUITS.items():
        for moment in ("matin", "soir"):
            pts = routes_circuit(circuit, moment)
            for i in range(len(pts) - 1):
                o, dst = pts[i], pts[i + 1]
                dur, dist = route_sync(o["lat"], o["lng"], dst["lat"], dst["lng"])
                cache[(cid, moment, i)] = {"duree_base_s": dur, "distance_routiere_m": dist,
                                          "n_legs": len(pts) - 1}
    return cache


def _meteo(rng, mois: int) -> str:
    """Météo échantillonnée par saison (hiver = plus de pluie/brouillard à Meknès)."""
    if mois in (11, 12, 1, 2, 3):          # saison humide
        p = [0.45, 0.20, 0.25, 0.10]
    elif mois in (4, 5, 10):
        p = [0.65, 0.20, 0.12, 0.03]
    else:                                   # Sep, Juin (secs)
        p = [0.80, 0.15, 0.04, 0.01]
    return rng.choice(list(F_METEO), p=p)


def _trafic(rng, heure: float) -> str:
    """Trafic échantillonné par heure : pointe 7–9h et 17–19h."""
    pointe = (7.0 <= heure <= 9.0) or (17.0 <= heure <= 19.0)
    p = [0.10, 0.25, 0.35, 0.30] if pointe else [0.55, 0.30, 0.12, 0.03]
    return rng.choice(list(F_TRAFIC), p=p)


def generer(seed: int | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed if seed is not None else settings.seed)
    debut = date.fromisoformat(settings.date_debut)
    jours = jours_ecole(debut, settings.n_jours)
    cache = _cache_tronçons()
    temb = settings.temps_embarquement_s

    lignes = []
    for jour in jours:
        j_ramadan = est_ramadan(jour)
        j_souk = jour_souk(jour)                    # souk hebdomadaire (mercredi)
        for moment in ("matin", "soir"):
            heure0 = (7.5 if moment == "matin" else 17.5) + float(rng.normal(0, 0.25))
            meteo = _meteo(rng, jour.month)
            trafic = _trafic(rng, heure0)
            f_meteo, f_trafic = F_METEO[meteo], F_TRAFIC[trafic]
            f_ramadan = (1.25 if moment == "soir" else 1.05) if j_ramadan else 1.0
            f_souk = 1.12 if j_souk else 1.0

            for cid, circuit in CIRCUITS.items():
                n_legs = cache[(cid, moment, 0)]["n_legs"]
                # Incident éventuel sur CE trajet (circuit+moment), placé sur un tronçon au hasard
                incident = None
                leg_incident = -1
                if rng.random() < settings.incident_rate:
                    incident = rng.choice(list(INCIDENTS))
                    leg_incident = (0 if incident in ("absence_chauffeur", "retard_admin")
                                    else int(rng.integers(0, n_legs)))
                travaux = int(rng.random() < 0.08)
                f_travaux = 1.30 if travaux else 1.0

                occ = 0.0 if moment == "matin" else CAPACITE_BUS * float(rng.uniform(0.7, 1.0))
                retard_cumule_s = 0.0
                for i in range(n_legs):
                    base = cache[(cid, moment, i)]
                    dur_base = base["duree_base_s"]

                    # Montées / descentes (dwell)
                    if moment == "matin":
                        montees = int(rng.poisson(6)) if i < n_legs - 1 else 0
                        descentes = 0
                        occ = min(CAPACITE_BUS, occ + montees)
                    else:
                        montees = 0
                        descentes = int(rng.poisson(6)) if i > 0 else 0
                        occ = max(0, occ - descentes)
                    dwell_s = (montees + descentes) * temb
                    taux_occ = round(occ / CAPACITE_BUS, 3)

                    combo = f_trafic * f_meteo * f_ramadan * f_souk * f_travaux
                    normal_s = dur_base * combo + dwell_s
                    bruit = float(rng.normal(0, settings.bruit_pct * normal_s))
                    reel_s = max(5.0, normal_s + bruit)

                    inc_type = "none"
                    if incident is not None and i == leg_incident:
                        lo, hi = INCIDENTS[incident]
                        reel_s += float(rng.uniform(lo, hi)) * 60.0
                        inc_type = incident

                    lignes.append({
                        "date": jour.isoformat(),
                        "jour_semaine": jour.weekday(),
                        "mois": jour.month,
                        "moment": moment,
                        "heure_depart": round(heure0 + i * 0.05, 3),
                        "meteo": meteo,
                        "trafic": trafic,
                        "ramadan": j_ramadan,
                        "jour_souk": j_souk,
                        "travaux_prevus": travaux,
                        "circuit_id": cid,
                        "leg_id": i,
                        "traverse_oued": circuit["traverse_oued"],
                        "nb_feux": circuit["nb_feux"],
                        "distance_routiere_m": round(base["distance_routiere_m"], 1),
                        "duree_base_s": round(dur_base, 1),
                        "nb_arrets_restants": n_legs - 1 - i,
                        "nb_montees": montees,
                        "nb_descentes": descentes,
                        "taux_occupation": taux_occ,
                        "retard_cumule_s": round(retard_cumule_s, 1),
                        "incident_type": inc_type,
                        "duree_reelle_min": round(reel_s / 60.0, 3),
                    })
                    retard_cumule_s += (reel_s - dur_base)

    df = pd.DataFrame(lignes)

    # Feature historique SANS FUITE : moyenne des durées réalisées des jours PASSÉS
    # (même circuit / moment / tronçon), via moyenne glissante décalée d'un cran.
    df = df.sort_values(["circuit_id", "moment", "leg_id", "date"]).reset_index(drop=True)
    grp = df.groupby(["circuit_id", "moment", "leg_id"])["duree_reelle_min"]
    hist_min = grp.transform(lambda s: s.expanding().mean().shift(1))
    df["duree_moyenne_historique_s"] = (hist_min * 60.0).fillna(df["duree_base_s"]).round(1)

    return df.sort_values(["date", "moment", "circuit_id", "leg_id"]).reset_index(drop=True)


def main():
    import os
    os.makedirs(settings.data_dir, exist_ok=True)
    df = generer()
    df.to_csv(settings.dataset_path, index=False)
    stats = {
        "lignes": len(df),
        "jours": df["date"].nunique(),
        "circuits": int(df["circuit_id"].nunique()),
        "part_incidents_%": round(100 * (df["incident_type"] != "none").mean(), 2),
        "cible_min": {"moy": round(df["duree_reelle_min"].mean(), 2),
                      "p50": round(df["duree_reelle_min"].median(), 2),
                      "p99": round(df["duree_reelle_min"].quantile(0.99), 2),
                      "max": round(df["duree_reelle_min"].max(), 2)},
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"→ écrit : {settings.dataset_path}")


if __name__ == "__main__":
    main()
