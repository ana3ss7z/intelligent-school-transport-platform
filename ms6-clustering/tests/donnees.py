"""
Chargement des données de test — les VRAIES données du projet, pas un jeu inventé.

Les 300 élèves de Meknès et la matrice routière OSRM sont déjà en cache dans `data/`. Les tests
s'en servent directement : un test qui tourne sur des points aléatoires ne dirait rien du service.

Tout est mis en cache au niveau du module : le chargement de la matrice 300×300 et la projection
UTM n'ont pas à être refaits à chaque test.
"""
from __future__ import annotations

import functools
import os

import numpy as np
import pandas as pd

import features as feat

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CAPACITE = 50


@functools.lru_cache(maxsize=1)
def jeu_complet():
    """(ids, XY projeté en mètres, matrice routière OSRM) pour les 300 élèves, triés par id."""
    df = pd.read_csv(os.path.join(DATA, "eleves_meknes.csv"))
    XY, _ = feat.projeter_metres(df[["latitude", "longitude"]].to_numpy(float))
    ROAD = np.load(os.path.join(DATA, "osrm_dist_m.npy"))
    return df["id"].to_numpy(), XY, ROAD


def permuter(perm: np.ndarray):
    """Rejoue le jeu complet dans un autre ordre de lignes.

    C'est exactement la variation qui fait basculer le nombre de bus en production : MS2 renvoie
    les élèves dans l'ordre du tas PostgreSQL, qui change à chaque mise à jour.
    """
    ids, XY, ROAD = jeu_complet()
    return ids[perm], XY[perm], ROAD[np.ix_(perm, perm)]


def ordres(n_permutations: int = 12, graine: int = 100):
    """Une liste d'ordres à tester : l'ordre trié, puis des permutations reproductibles."""
    ids, _, _ = jeu_complet()
    n = len(ids)
    out = [("trie_par_id", np.arange(n))]
    for s in range(n_permutations):
        out.append((f"permutation_{s}", np.random.default_rng(graine + s).permutation(n)))
    return out
