"""
Orchestrateur de clustering MS6.

Production (recommandé, cf. notebook 3) :
    production_clustering() — k-médoïdes capacitaire sur distance ROUTIÈRE OSRM (repli euclidien),
    détection + traitement séparé des élèves dispersés, choix du nombre de bus par Pareto.

Exploratoire / rétrocompatibilité :
    run_kmeans(), run_dbscan(), comparer() — désormais géographiquement corrects (projection mètres).
"""
import asyncio
import logging
import math
from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score

from config import settings
from features import (extraire_coords, projeter_metres,
                      matrice_euclidienne, matrice_haversine)
from algorithms import (kmeans as _kmeans, estimer_eps, dbscan_precomputed,
                        kmedoids_capacitaire, affectation_capacitaire)
from selection import pareto, choisir_k
from evaluation import evaluer

logger = logging.getLogger(__name__)


@dataclass
class ClusteringResult:
    methode: str
    k: int
    silhouette: float | None
    labels: dict[int, int]            # {eleve_id: groupe_id (1-indexé ; bruit -> 999)}
    metrics: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)


# ── Production : k-médoïdes capacitaire routier ──────────────────────────────
def _compute_production(ids, XY, D, capacity, k_margin, min_sil, iters) -> dict:
    """Cœur synchrone (CPU) de la stratégie de production. D = matrice de distances (m)."""
    n = len(ids)

    # 1) Détection des dispersés (bruit DBSCAN sur la matrice de distances)
    eps = estimer_eps(D, min_samples=5, percentile=90)
    noise = dbscan_precomputed(D, eps, 5) == -1
    core_idx = np.where(~noise)[0]
    # Garde-fou : assez d'élèves « cœur » pour former au moins ⌈n/cap⌉ groupes
    if len(core_idx) < max(2, math.ceil(n / capacity)):
        core_idx = np.arange(n)
        noise = np.zeros(n, dtype=bool)

    Dc = D[np.ix_(core_idx, core_idx)]
    XYc = XY[core_idx]

    # 2) Choix du nombre de bus (Pareto) sur le CŒUR — non distordu par les dispersés.
    #    k_min basé sur l'effectif TOTAL pour garantir la capacité d'accueillir tout le monde.
    k_min_total = math.ceil(n / capacity)
    rows = pareto(Dc, XYc, capacity, k_min=k_min_total, k_margin=k_margin, iters=iters)
    best = choisir_k(rows, min_silhouette=min_sil)
    k = best["k"]
    medoids_global = [int(core_idx[m]) for m in best["medoids"]]

    # 3) Affectation GLOBALE capacitaire de TOUS les élèves (cœur + dispersés) aux médoïdes.
    #    Garantit taille ≤ capacité par construction (k·capacité ≥ n). Les dispersés vont au
    #    médoïde le plus proche disposant d'une place ; ils restent signalés (ramassage individuel).
    labels_all = affectation_capacitaire(D[:, medoids_global], capacity)
    disperses_idx = np.where(noise)[0]

    mapping = {int(ids[i]): int(labels_all[i]) + 1 for i in range(n)}
    metrics = evaluer(labels_all, capacity, D=D, medoids=medoids_global)   # métriques HONNÊTES (tous)
    pareto_summary = [{kk: r[kk] for kk in ("k", "silhouette", "compacite_med_m",
                                            "compacite_max_m", "taille_max", "faisable")}
                      for r in rows]
    return {
        "k": k, "mapping": mapping, "metrics": metrics,
        "n_disperses": int(noise.sum()),
        "disperses_ids": [int(ids[i]) for i in disperses_idx],
        "pareto": pareto_summary,
    }


async def production_clustering(eleves: list[dict], capacity: int | None = None,
                                 use_road: bool | None = None) -> ClusteringResult:
    ids, latlon = extraire_coords(eleves)
    if len(ids) < 2:
        raise ValueError("Pas assez d'élèves pour le clustering (min 2)")
    capacity = capacity or settings.bus_capacity
    use_road = settings.use_road_distance if use_road is None else use_road

    XY, proj = projeter_metres(latlon)
    dist_src = "euclidienne (projetée)"
    if use_road:
        try:
            from osrm_client import matrice_routiere
            D = await matrice_routiere(latlon)
            dist_src = "routière (OSRM)"
        except Exception as exc:
            logger.warning("[MS6] OSRM indisponible (%s) — repli distance euclidienne", exc)
            D = matrice_euclidienne(XY)
            dist_src = "euclidienne (repli OSRM)"
    else:
        D = matrice_euclidienne(XY)

    res = await asyncio.to_thread(
        _compute_production, ids, XY, D, capacity,
        settings.k_margin, settings.min_silhouette, settings.kmedoids_iters)

    logger.info("[MS6] Production : k=%d bus, distance=%s, silhouette=%s, dispersés=%d",
                res["k"], dist_src, res["metrics"].get("silhouette"), res["n_disperses"])
    return ClusteringResult(
        methode=f"kmedoids_capacitaire ({dist_src})",
        k=res["k"], silhouette=res["metrics"].get("silhouette"),
        labels=res["mapping"], metrics=res["metrics"],
        extra={"distance": dist_src, "projection": proj, "capacity": capacity,
               "n_disperses": res["n_disperses"], "disperses_ids": res["disperses_ids"],
               "pareto": res["pareto"]})


async def pareto_flotte(eleves: list[dict], capacity: int | None = None,
                        use_road: bool | None = None) -> dict:
    """Renvoie uniquement la courbe de Pareto (qualité/compacité vs nombre de bus)."""
    res = await production_clustering(eleves, capacity, use_road)
    return {"capacity": res.extra["capacity"], "distance": res.extra["distance"],
            "k_retenu": res.k, "pareto": res.extra["pareto"]}


# ── Exploratoire / rétrocompatibilité (projection mètres) ────────────────────
def run_kmeans(eleves: list[dict]) -> ClusteringResult:
    """K-Means géographique : teste k=k_min..k_max, retient le meilleur Silhouette (espace mètres)."""
    ids, latlon = extraire_coords(eleves)
    if len(ids) < 2:
        raise ValueError("Pas assez d'élèves pour le clustering (min 2)")
    XY, _ = projeter_metres(latlon)
    best = (settings.k_min, -1.0, None)
    for k in range(settings.k_min, settings.k_max + 1):
        lab = _kmeans(XY, k)
        if len(set(lab)) < 2:
            continue
        s = silhouette_score(XY, lab)
        if s > best[1]:
            best = (k, s, lab)
    if best[2] is None:
        raise ValueError("K-Means n'a produit aucun résultat valide")
    k, s, lab = best
    mapping = {int(ids[i]): int(lab[i]) + 1 for i in range(len(ids))}
    return ClusteringResult("kmeans", k, round(float(s), 4), mapping,
                            metrics=evaluer(lab, settings.bus_capacity, XY=XY))


def run_dbscan(eleves: list[dict]) -> ClusteringResult:
    """DBSCAN sur distances projetées (mètres). Bruit -> groupe 999."""
    ids, latlon = extraire_coords(eleves)
    if len(ids) < 2:
        raise ValueError("Pas assez d'élèves pour le clustering (min 2)")
    XY, _ = projeter_metres(latlon)
    eps_m = settings.dbscan_eps * 1000.0      # config en km -> mètres
    lab = DBSCAN(eps=eps_m, min_samples=settings.dbscan_min_samples).fit_predict(XY)
    n_clusters = len(set(lab)) - (1 if -1 in lab else 0)
    s = None
    nn = lab != -1
    if n_clusters >= 2 and nn.sum() >= 2:
        s = round(float(silhouette_score(XY[nn], lab[nn])), 4)
    mapping = {int(ids[i]): (999 if lab[i] == -1 else int(lab[i]) + 1) for i in range(len(ids))}
    return ClusteringResult("dbscan", n_clusters, s, mapping,
                            metrics=evaluer(lab, settings.bus_capacity, XY=XY))


def comparer(eleves: list[dict]) -> dict:
    """Compare K-Means et DBSCAN (Silhouette). Conserve la forme de réponse historique."""
    km = run_kmeans(eleves)
    db = run_dbscan(eleves)
    gagnant = "kmeans" if (km.silhouette or -1) >= (db.silhouette or -1) else "dbscan"
    return {
        "kmeans": {"k": km.k, "silhouette": km.silhouette, "labels": km.labels},
        "dbscan": {"k": db.k, "silhouette": db.silhouette, "labels": db.labels},
        "gagnant": gagnant,
    }


def diagnostics(eleves: list[dict]) -> dict:
    """Stats EDA rapides + nombre de bus recommandé (⌈n/capacité⌉)."""
    ids, latlon = extraire_coords(eleves)
    n = len(ids)
    XY, proj = projeter_metres(latlon) if n else (np.empty((0, 2)), "n/a")
    emprise = {"x_m": round(float(np.ptp(XY[:, 0])), 0), "y_m": round(float(np.ptp(XY[:, 1])), 0)} if n else {}
    return {
        "n_eleves": n,
        "projection": proj,
        "emprise_m": emprise,
        "capacite_bus": settings.bus_capacity,
        "k_recommande": math.ceil(n / settings.bus_capacity) if n else 0,
        "use_road_distance": settings.use_road_distance,
    }
