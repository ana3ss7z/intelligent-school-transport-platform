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
def _greedy_capacitaire(C: np.ndarray, cap: int, rayon_max: float = 0.0) -> np.ndarray:
    """Repli glouton (toujours faisable) : chaque point au médoïde le plus proche ayant de la place
    et à ≤ rayon_max. Retourne des labels (−1 = non affecté / dispersé)."""
    m, k = C.shape
    labels = -np.ones(m, dtype=int)
    load = np.zeros(k, dtype=int)
    for i in np.argsort(C.min(1)):                 # les plus « faciles » d'abord
        for j in np.argsort(C[i]):
            if (not rayon_max or C[i, j] <= rayon_max) and load[j] < cap:
                labels[i] = j; load[j] += 1; break
    return labels


def affectation_capacitaire(C: np.ndarray, cap: int, rayon_max: float = 0.0) -> np.ndarray:
    """
    Affecte n points à k médoïdes en minimisant le coût total, sous taille ≤ cap par groupe.
    Problème de transport (flot à coût minimal) résolu en LP ; solution entière (0/1).
    Si `rayon_max` > 0 : les arcs de coût > rayon_max sont INTERDITS, et les points sans aucun médoïde
    à ≤ rayon_max sont marqués **dispersés** (label −1). Repli glouton si le LP est infaisable.
    C : matrice de coûts (n, k). Retourne les labels (n,) avec −1 = dispersé.
    """
    n, k = C.shape
    labels = -np.ones(n, dtype=int)

    joignable = (C.min(1) <= rayon_max) if rayon_max and rayon_max > 0 else np.ones(n, dtype=bool)
    idx = np.where(joignable)[0]
    m = len(idx)
    if m == 0:
        return labels
    Csub = C[idx]

    if k * cap < m:
        raise ValueError(f"Capacité totale insuffisante : {k}×{cap} < {m}")

    A_eq = sp.lil_matrix((m, m * k))
    for i in range(m):
        A_eq[i, i * k:(i + 1) * k] = 1             # chaque élève affecté à exactement 1 groupe
    A_ub = sp.lil_matrix((k, m * k))
    for j in range(k):
        A_ub[j, j::k] = 1                          # taille de chaque groupe ≤ cap

    if rayon_max and rayon_max > 0:                 # bornes par variable : arcs > R interdits (0,0)
        bounds = [(0, 0) if Csub[i, j] > rayon_max else (0, 1) for i in range(m) for j in range(k)]
    else:
        bounds = (0, 1)

    res = linprog(Csub.ravel(), A_ub=A_ub.tocsr(), b_ub=np.full(k, cap),
                  A_eq=A_eq.tocsr(), b_eq=np.ones(m), bounds=bounds, method="highs")
    if res.success:
        labels[idx] = res.x.reshape(m, k).argmax(1)
    else:
        logger.warning("[MS6] LP capacitaire infaisable (rayon=%.0f) — repli glouton", rayon_max or 0)
        labels[idx] = _greedy_capacitaire(Csub, cap, rayon_max)
    return labels


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
                          iters: int = 6, seed: int = 42, rayon_max: float = 0.0) -> tuple[np.ndarray, list[int]]:
    """
    k-médoïdes capacitaire sur matrice de distances D (routière ou euclidienne).
    Initialisation des médoïdes via K-Means sur XY_init, puis itérations
    (affectation capacitaire ↔ mise à jour des médoïdes).
    `rayon_max` > 0 : contrainte de rayon (distance max au médoïde) ; les points trop loin → dispersés (−1).
    """
    base = KMeans(n_clusters=k, random_state=seed, n_init=10).fit_predict(XY_init)
    medoids = _medoides_centraux(D, base, k, fallback=list(range(k)))
    labels = base
    for _ in range(iters):
        labels = affectation_capacitaire(D[:, medoids], cap, rayon_max=rayon_max)
        nouveaux = _medoides_centraux(D, labels, k, fallback=medoids)
        if set(nouveaux) == set(medoids):
            break
        medoids = nouveaux
    return labels, medoids
