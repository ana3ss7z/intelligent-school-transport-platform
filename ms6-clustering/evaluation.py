"""
Évaluation multi-critères des partitions (cf. notebooks 1–3).
Fonctionne en distance euclidienne (espace projeté) ou précalculée (routière).
"""
import numpy as np
from sklearn.metrics import (
    silhouette_score, davies_bouldin_score, calinski_harabasz_score,
)


def _intra_medoides(D: np.ndarray, labels: np.ndarray, medoids: list[int]) -> np.ndarray:
    """Distance de chaque point AFFECTÉ à son médoïde (matrice précalculée ; ignore les dispersés −1)."""
    return np.array([D[i, medoids[labels[i]]] for i in range(len(labels)) if labels[i] >= 0], dtype=float)


def evaluer(labels: np.ndarray, capacity: int,
            XY: np.ndarray | None = None,
            D: np.ndarray | None = None,
            medoids: list[int] | None = None) -> dict:
    """
    Métriques internes + KPI métier. Fournir soit XY (euclidien) soit D (précalculé/routier).
    Le bruit (label == -1) est exclu des indices internes.
    """
    labels = np.asarray(labels)
    mask = labels != -1
    uniq = sorted(set(labels[mask]))
    sizes = [int((labels == c).sum()) for c in uniq]
    ok = len(uniq) >= 2

    precomputed = D is not None
    if ok:
        if precomputed:
            sub = D[np.ix_(mask, mask)]
            sil = silhouette_score(sub, labels[mask], metric="precomputed")
        else:
            sil = silhouette_score(XY[mask], labels[mask])
            db = davies_bouldin_score(XY[mask], labels[mask])
            ch = calinski_harabasz_score(XY[mask], labels[mask])
    else:
        sil = float("nan")

    res = {
        "n_clusters": len(uniq),
        "n_bruit": int((labels == -1).sum()),
        "silhouette": round(float(sil), 4) if ok else None,
        "taille_min": min(sizes) if sizes else 0,
        "taille_max": max(sizes) if sizes else 0,
        "cv_tailles": round(float(np.std(sizes) / np.mean(sizes)), 4) if sizes else None,
        "faisabilite_capacite_%": round(100.0 * np.mean([s <= capacity for s in sizes]), 1) if sizes else 0.0,
        "faisable": bool(sizes and max(sizes) <= capacity),
    }
    if not precomputed and ok:
        res["davies_bouldin"] = round(float(db), 4)
        res["calinski_harabasz"] = round(float(ch), 4)

    # Compacité (distance au médoïde si fourni, sinon au centroïde)
    if medoids is not None and precomputed:
        d = _intra_medoides(D, labels, medoids)
        if len(d):
            res["compacite_med_m"] = round(float(np.median(d)), 1)
            res["compacite_max_m"] = round(float(d.max()), 1)
    elif XY is not None:
        ds = []
        for c in uniq:
            pts = XY[labels == c]
            ds += list(np.linalg.norm(pts - pts.mean(0), axis=1))
        if ds:
            res["compacite_med_m"] = round(float(np.median(ds)), 1)
            res["compacite_max_m"] = round(float(np.max(ds)), 1)
    return res
