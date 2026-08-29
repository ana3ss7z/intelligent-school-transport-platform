"""Rejoue le balayage du rayon maximal sur le code de production ACTUEL.

Pourquoi ce script existe
-------------------------
Le balayage du notebook `06_rayon_max_study.ipynb` date d'AVANT le correctif de
`choisir_k` du 24/08 : sa ligne « rayon désactivé » donnait `k = 8` et une
silhouette de 0,4056, là où le service produit aujourd'hui `k = 7` à 0,4256.
La conclusion de l'étude (un rayon plus serré améliore l'indice en EXCLUANT des
élèves) ne dépend pas de `k`, mais la première ligne du tableau, elle,
contredisait la production.

Ce script reprend exactement les cellules 4 et 6 du notebook et écrit
`data/rayon_sweep_resultats.json`.

Pré-requis : aucun service. La matrice routière OSRM est lue depuis le cache
`data/osrm_dist_m.npy`.
Aucune écriture ailleurs que dans ce JSON : `production_config.json` et
`quality_baseline.json` ne sont pas touchés.

    cd ms6-clustering && python rejouer_rayon.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import config
from clustering import _compute_production
from features import extraire_coords, matrice_euclidienne, projeter_metres

ICI = Path(__file__).resolve().parent
SORTIE = ICI / "data" / "rayon_sweep_resultats.json"
RAYONS = [0, 2500, 2000, 1500, 1200, 1000, 800]
CAP = 50


def main():
    df = pd.read_csv(ICI / "data" / "eleves_meknes.csv")
    eleves = [{"id": int(r.id), "latitude": float(r.latitude),
               "longitude": float(r.longitude)} for r in df.itertuples()]
    ids, latlon = extraire_coords(eleves)
    XY, proj = projeter_metres(latlon)
    try:
        D = np.load(ICI / "data" / "osrm_dist_m.npy")
        assert D.shape[0] == len(ids)
        dist_src = "routière OSRM (cache)"
    except Exception:
        D = matrice_euclidienne(XY)
        dist_src = "euclidienne (repli)"
    print(f"{len(ids)} élèves · distances {dist_src} · projection {proj}")

    KM = config.settings.k_margin
    MS = config.settings.min_silhouette
    IT = config.settings.kmedoids_iters

    balayage = []
    for R in RAYONS:
        res = _compute_production(ids, XY, D, CAP, KM, MS, IT, rayon_max=R)
        m = res["metrics"]
        balayage.append({
            "rayon_m": R or None,
            "libelle": "∞ (off)" if not R else str(R),
            "k_bus": res["k"],
            "compacite_max_m": m.get("compacite_max_m"),
            "compacite_med_m": m.get("compacite_med_m"),
            "non_affectes": res["n_non_affectes"],
            "silhouette": m.get("silhouette"),
            "taille_max": m.get("taille_max"),
        })
        print(f"  rayon {balayage[-1]['libelle']:>8s} : k={res['k']} · "
              f"silhouette {m.get('silhouette')} · "
              f"non affectés {res['n_non_affectes']} · "
              f"compacité max {m.get('compacite_max_m')} m")

    ligne_off = balayage[0]
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "_provenance": f"Rejoué par rejouer_rayon.py le {datetime.now(timezone.utc):%Y-%m-%d} "
                       "sur le code de production actuel (après le correctif de choisir_k du "
                       "24/08). Remplace le balayage d'origine, dont la ligne « rayon "
                       "désactivé » donnait k=8 et ne correspondait plus au service.",
        "_contrainte": "Le rayon est la distance routière maximale autorisée entre un élève et le "
                       "médoïde de son groupe. C'est une contrainte DURE : les arcs plus longs "
                       "sont interdits dans le LP, et un élève sans bus à portée devient « non "
                       "affecté », c'est-à-dire à ramasser individuellement.",
        "date_execution": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_eleves": len(ids),
        "capacite": CAP,
        "distances": dist_src,
        "reference_production": {
            "_note": "La ligne « rayon désactivé » EST la configuration de production. "
                     "Elle doit donc reproduire ce que le service publie.",
            "k_bus": ligne_off["k_bus"],
            "silhouette": ligne_off["silhouette"],
        },
        "balayage": balayage,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nécrit : {SORTIE}")
    print(f"ligne « rayon désactivé » : k={ligne_off['k_bus']}, "
          f"silhouette {ligne_off['silhouette']}")


if __name__ == "__main__":
    main()
