"""
Moteur de clustering géographique pour les élèves de Meknès.
- K-Means : teste k=3..5, retient le meilleur Silhouette Score
- DBSCAN  : distance Haversine (vraie distance sphérique en km)
- Résultat : {eleve_id: groupe_id}
"""
import logging
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from config import settings

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0


@dataclass
class ClusteringResult:
    methode: str
    k: int
    silhouette: float
    labels: dict[int, int]   # {eleve_id: groupe_id (1-indexed)}


def _coordonnees(eleves: list[dict]) -> tuple[list[int], np.ndarray]:
    ids, coords = [], []
    for e in eleves:
        lat = e.get("latitude")
        lon = e.get("longitude")
        if lat is not None and lon is not None:
            ids.append(e["id"])
            coords.append([lat, lon])
    return ids, np.array(coords)


def run_kmeans(eleves: list[dict]) -> ClusteringResult:
    """
    K-Means géographique — teste k=k_min..k_max.
    Utilise StandardScaler pour normaliser lat/lon.
    """
    ids, coords = _coordonnees(eleves)
    if len(ids) < 2:
        raise ValueError("Pas assez d'élèves pour le clustering (min 2)")

    scaler = StandardScaler()
    X = scaler.fit_transform(coords)

    best_k, best_score, best_labels = settings.k_min, -1.0, None

    for k in range(settings.k_min, settings.k_max + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)

        if len(set(labels)) < 2:
            continue

        score = silhouette_score(X, labels)
        logger.info("[MS6] K-Means k=%d → Silhouette=%.4f", k, score)

        if score > best_score:
            best_score, best_k, best_labels = score, k, labels

    if best_labels is None:
        raise ValueError("K-Means n'a produit aucun résultat valide")

    logger.info("[MS6] K-Means meilleur k=%d Silhouette=%.4f", best_k, best_score)

    mapping = {eid: int(lbl) + 1 for eid, lbl in zip(ids, best_labels)}
    return ClusteringResult("kmeans", best_k, round(best_score, 4), mapping)


def run_dbscan(eleves: list[dict]) -> ClusteringResult:
    """
    DBSCAN avec distance Haversine (vraie distance sphérique).
    eps est en km (ex: 1.0 km), converti en radians pour sklearn.
    Les points bruit (label=-1) reçoivent groupeId=999.
    """
    ids, coords = _coordonnees(eleves)
    if len(ids) < 2:
        raise ValueError("Pas assez d'élèves pour le clustering (min 2)")

    # Haversine attend des coordonnées en RADIANS
    coords_rad = np.radians(coords)

    # eps en radians = distance_km / rayon_terre_km
    eps_rad = settings.dbscan_eps / EARTH_RADIUS_KM

    db = DBSCAN(
        eps=eps_rad,
        min_samples=settings.dbscan_min_samples,
        metric="haversine",
        algorithm="ball_tree",
    )
    labels = db.fit_predict(coords_rad)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_bruit = list(labels).count(-1)
    logger.info("[MS6] DBSCAN Haversine → %d clusters, %d points bruit", n_clusters, n_bruit)

    # Silhouette sur les points non-bruit uniquement
    non_noise = labels != -1
    score = -1.0
    if n_clusters >= 2 and non_noise.sum() >= 2:
        score = silhouette_score(coords_rad[non_noise], labels[non_noise], metric="haversine")
        logger.info("[MS6] DBSCAN Silhouette=%.4f", score)

    mapping = {eid: 999 if lbl == -1 else int(lbl) + 1 for eid, lbl in zip(ids, labels)}
    return ClusteringResult("dbscan", n_clusters, round(score, 4), mapping)


def comparer(eleves: list[dict]) -> dict:
    """Lance K-Means ET DBSCAN, compare les Silhouette Scores."""
    km = run_kmeans(eleves)
    db = run_dbscan(eleves)

    gagnant = "kmeans" if km.silhouette >= db.silhouette else "dbscan"
    logger.info(
        "[MS6] KMeans=%.4f vs DBSCAN=%.4f → gagnant=%s",
        km.silhouette, db.silhouette, gagnant,
    )

    return {
        "kmeans": {"k": km.k, "silhouette": km.silhouette, "labels": km.labels},
        "dbscan": {"k": db.k, "silhouette": db.silhouette, "labels": db.labels},
        "gagnant": gagnant,
    }