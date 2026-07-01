"""
Algorithmes de clustering pour MS6.

- Exploratoires (endpoints legacy / benchmark) : K-Means, K-Means capacitaire, DBSCAN.
- Production : k-médoïdes capacitaire sur matrice de distances (routière OSRM ou euclidienne),
  avec affectation par flot à coût minimal (problème de transport résolu en LP, solution entière).
"""
import logging

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog
from sklearn.cluster import DBSCAN, KMeans
from sklearn.neighbors import NearestNeighbors

logger = logging.getLogger(__name__)


# ── Exploratoire ─────────────────────────────────────────────────────────────
def kmeans(XY: np.ndarray, k: int, seed: int = 42) -> np.ndarray:
    return KMeans(n_clusters=k, random_state=seed, n_init=10).fit_predict(XY)


def kmeans_capacitaire(XY: np.ndarray, k: int, size_max: int, seed: int = 42) -> np.ndarray:
    """Groupes de taille ≤ size_max. Utilise k-means-constrained ; repli glouton si absent."""
    try:
        from k_means_constrained import KMeansConstrained
        return KMeansConstrained(n_clusters=k, size_max=size_max,
                                 random_state=seed, n_init=10).fit_predict(XY)
    except Exception as exc:
        logger.warning("[MS6] k-means-constrained indisponible (%s) — repli glouton", exc)
        base = KMeans(n_clusters=k, random_state=seed, n_init=10).fit(XY)
        d = np.linalg.norm(XY[:, None] - base.cluster_centers_[None], axis=2)
        cap = {c: 0 for c in range(k)}
        lab = -np.ones(len(XY), dtype=int)
        for i in np.argsort(d.min(1)):
            for c in np.argsort(d[i]):
                if cap[c] < size_max:
                    lab[i] = c
                    cap[c] += 1
                    break
        return lab


def estimer_eps(D: np.ndarray, min_samples: int = 5, percentile: float = 90) -> float:
    """eps DBSCAN à partir de la distance au k-ᵉ voisin (matrice précalculée)."""
    n = len(D)
    kd = np.sort(np.partition(D + np.eye(n) * 1e12, min_samples - 1, axis=1)[:, min_samples - 1])
    return float(np.percentile(kd, percentile))


def dbscan_precomputed(D: np.ndarray, eps: float, min_samples: int = 5) -> np.ndarray:
    return DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed").fit_predict(D)


# ── Production : k-médoïdes capacitaire ──────────────────────────────────────
def affectation_capacitaire(C: np.ndarray, cap: int) -> np.ndarray:
    """
    Affecte n points à k médoïdes en minimisant le coût total, sous taille ≤ cap par groupe.
    Problème de transport (flot à coût minimal) résolu en LP ; la solution est entière (0/1).
    C : matrice de coûts (n, k). Retourne les labels (n,).
    """
    n, k = C.shape
    if k * cap < n:
        raise ValueError(f"Capacité totale insuffisante : {k}×{cap} < {n}")
    A_eq = sp.lil_matrix((n, n * k))
    for i in range(n):
        A_eq[i, i * k:(i + 1) * k] = 1            # chaque élève affecté à exactement 1 groupe
    A_ub = sp.lil_matrix((k, n * k))
    for j in range(k):
        A_ub[j, j::k] = 1                          # taille de chaque groupe ≤ cap
    res = linprog(C.ravel(), A_ub=A_ub.tocsr(), b_ub=np.full(k, cap),
                  A_eq=A_eq.tocsr(), b_eq=np.ones(n), bounds=(0, 1), method="highs")
    if not res.success:
        raise RuntimeError(f"LP affectation échouée : {res.message}")
    return res.x.reshape(n, k).argmax(1)


def _medoides_centraux(D: np.ndarray, labels: np.ndarray, k: int, fallback: list[int]) -> list[int]:
    medoids = []
    for j in range(k):
        membres = np.where(labels == j)[0]
        if len(membres) == 0:
            medoids.append(fallback[j])
            continue
        sub = D[np.ix_(membres, membres)]
        medoids.append(int(membres[sub.sum(1).argmin()]))
    return medoids


def kmedoids_capacitaire(D: np.ndarray, k: int, cap: int, XY_init: np.ndarray,
                          iters: int = 6, seed: int = 42) -> tuple[np.ndarray, list[int]]:
    """
    k-médoïdes capacitaire sur matrice de distances D (routière ou euclidienne).
    Initialisation des médoïdes via K-Means sur XY_init, puis itérations
    (affectation capacitaire ↔ mise à jour des médoïdes).
    """
    base = KMeans(n_clusters=k, random_state=seed, n_init=10).fit_predict(XY_init)
    medoids = _medoides_centraux(D, base, k, fallback=list(range(k)))
    labels = base
    for _ in range(iters):
        labels = affectation_capacitaire(D[:, medoids], cap)
        nouveaux = _medoides_centraux(D, labels, k, fallback=medoids)
        if set(nouveaux) == set(medoids):
            break
        medoids = nouveaux
    return labels, medoids
