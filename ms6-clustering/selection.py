"""
Sélection du nombre de bus (k) pour la stratégie de production.

Balaye k de ⌈n/capacité⌉ à +marge (courbe de Pareto qualité/compacité vs flotte), puis choisit le
plus petit k atteignant le seuil de silhouette, sinon le k de meilleure silhouette (genou).
"""
import math
import logging

import numpy as np

from algorithms import kmedoids_capacitaire
from evaluation import evaluer

logger = logging.getLogger(__name__)


def pareto(D: np.ndarray, XY: np.ndarray, capacity: int, k_min: int | None = None,
           k_margin: int = 3, iters: int = 6) -> list[dict]:
    """
    Pour chaque k, calcule la partition capacitaire et ses métriques (routières/euclidiennes).
    k_min : nombre de bus minimal (par défaut ⌈n/capacité⌉ ; on peut imposer un k_min plus grand
            pour réserver de la capacité aux élèves dispersés ajoutés ensuite).
    Retourne une liste de dicts {k, labels, medoids, metrics...}.
    """
    n = len(D)
    if k_min is None:
        k_min = math.ceil(n / capacity)
    out = []
    for k in range(k_min, k_min + k_margin + 1):
        if k * capacity < n:
            continue
        labels, medoids = kmedoids_capacitaire(D, k, capacity, XY, iters=iters)
        m = evaluer(labels, capacity, D=D, medoids=medoids)
        out.append({"k": k, "labels": labels, "medoids": medoids, **m})
    return out


def choisir_k(pareto_rows: list[dict], min_silhouette: float = 0.50) -> dict:
    """
    Choix : plus petit k faisable dont la silhouette ≥ seuil ; sinon meilleure silhouette.
    Retourne la ligne Pareto retenue.
    """
    faisables = [r for r in pareto_rows if r["faisable"]]
    if not faisables:
        faisables = pareto_rows
    passe = [r for r in faisables if (r["silhouette"] or -1) >= min_silhouette]
    if passe:
        return min(passe, key=lambda r: r["k"])
    return max(faisables, key=lambda r: (r["silhouette"] or -1))
