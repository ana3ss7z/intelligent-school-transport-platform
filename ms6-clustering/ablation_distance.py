"""
MS6 — faire entrer l'algorithme de production dans l'arène, et isoler l'apport de la distance routière.

Deux trous que ce module comble
-------------------------------
**1. Le benchmark ne justifiait pas le choix de production.** `02_model_comparison.ipynb` compare
dix algorithmes et couronne OPTICS (score composite 0,931) — un algorithme qui produit seize
mini-groupes et cinquante-deux points de bruit, donc inutilisable pour remplir des bus. Le choix de
production y est d'ailleurs **écrit en dur** dans le notebook, il ne découle pas du score. Surtout,
l'algorithme réellement déployé — **k-médoïdes capacitaire routier** — n'est dans **aucun** des dix.

**2. L'apport de la distance routière n'était pas isolé.** `03_production_strategy.ipynb` compare
bien « euclidien k=6/k=8 » à « routier k=7 », mais fait varier **deux à trois facteurs à la fois**
(la distance, l'algorithme et k). On ne peut rien conclure d'une telle comparaison. Or cette thèse
porte deux conclusions du projet : elle explique la qualité du clustering **et** le résultat du
benchmark CVRP de MS5 (« l'information géographique est injectée avant le routage »).

Règles du protocole appliquées ici
----------------------------------
- **Une seule matrice de référence** : la matrice routière OSRM en cache (`data/osrm_dist_m.npy`).
- **Tout le monde est noté avec la même règle** : silhouette et compacité sont calculées sur la
  matrice **routière**, quelle que soit la distance qui a servi à *construire* la partition. Sans
  cela, chaque méthode serait jugée à sa propre aune et l'euclidien gagnerait mécaniquement.
- **Un seul facteur varié** pour l'ablation : même algorithme, même k, même graine, seule la
  matrice change.
- **Des baselines naïves crédibles** : découpage par quartier et partition aléatoire équilibrée.
  Un jury demandera « votre k-médoïdes fait-il mieux qu'un découpage par quartier ? » — jusqu'ici
  le dossier n'avait pas de réponse.
- **Une métrique aval en minutes** : on fait tourner le TSP sur chaque partition et on compare le
  temps de conduite total. C'est la seule unité qui parle à une école.

    python ablation_distance.py     → rapport + data/ablation_distance.json
"""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pandas as pd

import algorithms as algo
import features as feat
from config import settings
from evaluation import evaluer

DATA = os.path.join(os.path.dirname(__file__), "data")
CAP = 50


# ─────────────────────── Chargement (100 % hors ligne) ───────────────────────
def charger():
    df = pd.read_csv(os.path.join(DATA, "eleves_meknes.csv"))
    latlon = df[["latitude", "longitude"]].to_numpy(float)
    XY, proj = feat.projeter_metres(latlon)
    ROAD = np.load(os.path.join(DATA, "osrm_dist_m.npy"))
    DUR = np.load(os.path.join(DATA, "osrm_dur_s.npy"))
    EUC = feat.matrice_euclidienne(XY)
    ecole = json.load(open(os.path.join(DATA, "school.json"), encoding="utf-8"))
    return df, latlon, XY, proj, ROAD, DUR, EUC, ecole


# ───────────────────────────── Partitionneurs ────────────────────────────────
def _medoides(D: np.ndarray, labels: np.ndarray) -> list[int]:
    """Médoïde routier de chaque groupe — recalculé pour TOUTES les partitions,
    y compris celles qui n'en utilisent pas, pour que la compacité soit comparable."""
    med = []
    for c in sorted(set(labels[labels >= 0])):
        membres = np.where(labels == c)[0]
        sub = D[np.ix_(membres, membres)]
        med.append(int(membres[sub.sum(1).argmin()]))
    return med


def part_kmedoides(D, XY, k, seed=42):
    labels, _ = algo.kmedoids_capacitaire(D, k, CAP, XY, iters=settings.kmedoids_iters
                                          if hasattr(settings, "kmedoids_iters") else 6, seed=seed)
    return labels


def part_kmeans(XY, k, seed=42):
    return algo.kmeans(XY, k, seed)


def part_kmeans_cap(XY, k, seed=42):
    return algo.kmeans_capacitaire(XY, k, CAP, seed)


def part_quartier(df: pd.DataFrame, k: int) -> np.ndarray:
    """Baseline naïve n° 1 : on regroupe par quartier, puis on empile les quartiers dans k bus.

    C'est la solution qu'une école mettrait en place sans data scientist : « le bus 1 fait Hamria,
    le bus 2 fait Marjane… ». Empilage glouton du plus gros quartier au plus petit, dans le bus le
    moins rempli — un quartier trop gros pour un bus est scindé.
    """
    labels = -np.ones(len(df), dtype=int)
    groupes = sorted(df.groupby("quartier").indices.items(), key=lambda kv: -len(kv[1]))
    charge = np.zeros(k, dtype=int)
    for _, idx in groupes:
        idx = list(idx)
        while idx:
            j = int(np.argmin(charge))
            place = CAP - charge[j]
            if place <= 0:
                j = int(np.argmin(charge))
                place = max(1, CAP - charge[j])
            prendre, idx = idx[:place], idx[place:]
            labels[prendre] = j
            charge[j] += len(prendre)
    return labels


def part_aleatoire(n: int, k: int, seed=42) -> np.ndarray:
    """Baseline naïve n° 2 : partition aléatoire équilibrée. Le plancher absolu —
    tout ce qui ne bat pas ça n'a aucune valeur géographique."""
    rng = np.random.default_rng(seed)
    ordre = rng.permutation(n)
    labels = np.empty(n, dtype=int)
    for rang, i in enumerate(ordre):
        labels[i] = rang % k
    return labels


# ───────────────────── Métrique aval : minutes de conduite ───────────────────
def _depot_osrm(latlon: np.ndarray, ecole: dict, timeout: float = 30.0):
    """Durées et distances routières école ↔ chaque élève.

    La matrice en cache ne couvre que les élèves entre eux ; il manque la ligne du dépôt. OSRM
    `/table` plafonnant à 100 coordonnées, on interroge par blocs — le même piège que celui
    rencontré dans le benchmark CVRP de MS5, et le même remède.
    """
    import httpx
    n = len(latlon)
    dur = np.zeros(n)
    dist = np.zeros(n)
    with httpx.Client(timeout=timeout) as cli:
        for debut in range(0, n, 90):
            bloc = latlon[debut:debut + 90]
            coords = f"{ecole['lng']},{ecole['lat']};" + ";".join(
                f"{lo},{la}" for la, lo in bloc)
            url = (f"{settings.osrm_url}/table/v1/driving/{coords}"
                   f"?sources=0&annotations=duration,distance")
            r = cli.get(url)
            r.raise_for_status()
            j = r.json()
            dur[debut:debut + len(bloc)] = j["durations"][0][1:]
            dist[debut:debut + len(bloc)] = j["distances"][0][1:]
    return dur, dist


def _tsp(M: np.ndarray, time_limit_s: int = 3) -> float:
    """TSP sur une matrice (0 = dépôt = école). Mêmes réglages que `ms5-planification/vrp.py`."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    n = len(M)
    if n <= 2:
        return float(M[0, 1] + M[1, 0]) if n == 2 else 0.0
    Mi = np.rint(M).astype(int)
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    idx = routing.RegisterTransitCallback(
        lambda a, b: int(Mi[manager.IndexToNode(a)][manager.IndexToNode(b)]))
    routing.SetArcCostEvaluatorOfAllVehicles(idx)
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    p.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    p.time_limit.FromSeconds(time_limit_s)
    sol = routing.SolveWithParameters(p)
    if sol is None:
        return float("nan")
    total, i = 0.0, routing.Start(0)
    while not routing.IsEnd(i):
        j = sol.Value(routing.NextVar(i))
        total += M[manager.IndexToNode(i)][manager.IndexToNode(j)]
        i = j
    return total


def _tsp_ordre(M: np.ndarray, time_limit_s: int = 3) -> tuple[float, list[int]]:
    """Comme `_tsp`, mais retourne aussi l'ordre de visite — nécessaire au temps à bord."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    n = len(M)
    if n <= 2:
        return (float(M[0, 1] + M[1, 0]) if n == 2 else 0.0), list(range(n))
    Mi = np.rint(M).astype(int)
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    idx = routing.RegisterTransitCallback(
        lambda a, b: int(Mi[manager.IndexToNode(a)][manager.IndexToNode(b)]))
    routing.SetArcCostEvaluatorOfAllVehicles(idx)
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    p.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    p.time_limit.FromSeconds(time_limit_s)
    sol = routing.SolveWithParameters(p)
    if sol is None:
        return float("nan"), []
    ordre, total, i = [], 0.0, routing.Start(0)
    while not routing.IsEnd(i):
        ordre.append(manager.IndexToNode(i))
        j = sol.Value(routing.NextVar(i))
        total += M[manager.IndexToNode(i)][manager.IndexToNode(j)]
        i = j
    return total, ordre


def metriques_tournees(labels: np.ndarray, DUR: np.ndarray, dur_depot: np.ndarray,
                       time_limit_s: int = 3) -> dict:
    """Deux métriques aval, et il faut les deux.

    - **Durée totale de la flotte** : ce que paie l'école (carburant, heures de chauffeur).
    - **Temps à bord par enfant** : ce que vit la famille. C'est *cette* grandeur que la compacité
      géographique est censée réduire, et c'est l'argument avancé pour le 7ᵉ bus dans le benchmark
      CVRP. Ne mesurer que la première reviendrait à évaluer MS6 sur un objectif qui n'est pas le sien.

    Le trajet est école → élèves → école (sens matin) : un enfant monte à son arrêt et reste à bord
    jusqu'à l'arrivée. Son temps à bord est donc la durée restante du circuit à partir de son arrêt.
    """
    total_min = 0.0
    a_bord: list[float] = []
    for c in sorted(set(labels[labels >= 0])):
        membres = np.where(labels == c)[0]
        m = len(membres)
        M = np.zeros((m + 1, m + 1))
        M[0, 1:] = dur_depot[membres]
        M[1:, 0] = dur_depot[membres]
        M[1:, 1:] = DUR[np.ix_(membres, membres)]
        duree_s, ordre = _tsp_ordre(M, time_limit_s)
        total_min += duree_s / 60.0
        # temps cumulé le long du circuit, puis temps restant jusqu'au retour à l'école
        cumul, t = {}, 0.0
        for a, b in zip(ordre, ordre[1:] + [0]):
            t += M[a][b]
            cumul[b] = t
        fin = t
        for noeud, t_arret in cumul.items():
            if noeud != 0:
                a_bord.append((fin - t_arret) / 60.0)
    a_bord_arr = np.array(a_bord) if a_bord else np.array([0.0])
    return {
        "duree_tournees_min": round(total_min, 1),
        "temps_a_bord_moyen_min": round(float(a_bord_arr.mean()), 1),
        "temps_a_bord_median_min": round(float(np.median(a_bord_arr)), 1),
        "temps_a_bord_p90_min": round(float(np.percentile(a_bord_arr, 90)), 1),
        "temps_a_bord_max_min": round(float(a_bord_arr.max()), 1),
    }


def duree_totale_tournees(labels: np.ndarray, DUR: np.ndarray,
                          dur_depot: np.ndarray, time_limit_s: int = 3) -> float:
    """Somme, sur tous les bus, du temps de conduite école → élèves → école (minutes)."""
    return metriques_tournees(labels, DUR, dur_depot, time_limit_s)["duree_tournees_min"]


# ──────────────────────────────── Campagne ───────────────────────────────────
def noter(labels: np.ndarray, ROAD: np.ndarray) -> dict:
    """Évalue une partition — TOUJOURS sur la matrice routière, quelle que soit son origine."""
    med = _medoides(ROAD, labels)
    return evaluer(labels, CAP, D=ROAD, medoids=med)


def pipeline_production(ids, XY, D):
    """Le chemin RÉELLEMENT exécuté par le service : dispersés DBSCAN → Pareto → affectation LP.

    On l'appelle directement (`_compute_production` est synchrone) plutôt que de le réimplémenter :
    un benchmark qui réécrit l'algorithme qu'il évalue ne mesure plus rien.
    """
    from clustering import _compute_production
    res = _compute_production(ids, XY, D, CAP, settings.k_margin,
                              settings.min_silhouette, settings.kmedoids_iters)
    labels = np.array([res["mapping"][int(i)] for i in ids])
    labels = np.where(labels == 999, -1, labels - 1)      # 999 = dispersé → -1
    return labels, res


def variance_graines(D, XY, k, ROAD, graines=range(10)) -> dict:
    """§1c — tout le service est figé à `random_state=42`. Les écarts de silhouette entre k=7,
    k=8 et k=9 valent 0,006 à 0,008 et sont traités comme des différences réelles. Ont-ils un
    sens face à la variabilité d'initialisation ?"""
    sils, comps, durees = [], [], []
    for s in graines:
        lab = part_kmedoides(D, XY, k, seed=s)
        m = noter(lab, ROAD)
        sils.append(m["silhouette"])
        comps.append(m.get("compacite_med_m", float("nan")))
    return {"k": k, "n_graines": len(sils),
            "silhouette_moy": round(float(np.mean(sils)), 4),
            "silhouette_ecart_type": round(float(np.std(sils)), 4),
            "silhouette_min": round(float(np.min(sils)), 4),
            "silhouette_max": round(float(np.max(sils)), 4),
            "compacite_med_moy": round(float(np.mean(comps)), 1)}


def main() -> None:
    df, latlon, XY, proj, ROAD, DUR, EUC, ecole = charger()
    n = len(df)
    k = 7                     # le k gelé en production (production_config.json)
    print(f"[MS6] {n} eleves | projection {proj} | k={k} | capacite {CAP}")
    print(f"[MS6] Matrice routiere en cache : {ROAD.shape} | "
          f"detour median route/vol d oiseau = "
          f"{np.median(ROAD[np.triu_indices(n,1)] / np.maximum(1, feat.matrice_haversine(latlon)[np.triu_indices(n,1)])):.2f}x\n")

    print("[MS6] Recuperation de la ligne du depot (ecole) aupres d OSRM...")
    dur_depot, dist_depot = _depot_osrm(latlon, ecole)
    print(f"       duree ecole->eleve : mediane {np.median(dur_depot)/60:.1f} min\n")

    concurrents = {
        "kmedoides_capacitaire_ROUTIER (production)": lambda: part_kmedoides(ROAD, XY, k),
        "kmedoides_capacitaire_EUCLIDIEN": lambda: part_kmedoides(EUC, XY, k),
        "kmeans_capacitaire (euclidien)": lambda: part_kmeans_cap(XY, k),
        "kmeans (euclidien, sans capacite)": lambda: part_kmeans(XY, k),
        "baseline_quartier": lambda: part_quartier(df, k),
        "baseline_aleatoire": lambda: part_aleatoire(n, k),
    }

    resultats = []
    for nom, f in concurrents.items():
        t0 = time.perf_counter()
        labels = f()
        t_part = time.perf_counter() - t0
        m = noter(labels, ROAD)
        m.update(metriques_tournees(labels, DUR, dur_depot))
        m["temps_partition_s"] = round(t_part, 2)
        m["methode"] = nom
        resultats.append(m)
        print(f"  {nom:44s} sil={m['silhouette']:.4f} "
              f"tournees={m['duree_tournees_min']:6.1f} min  "
              f"a_bord_moy={m['temps_a_bord_moyen_min']:5.1f} min")

    ref = next(r for r in resultats if r["methode"].startswith("kmedoides_capacitaire_ROUTIER"))
    print("\n## Arene (tout est note sur la matrice ROUTIERE)\n")
    print("| Methode | Silhouette | Compacite med. | Taille max | Faisable | "
          "Flotte (min) | vs prod | A bord moyen | A bord p90 |")
    print("|---|--:|--:|--:|:-:|--:|--:|--:|--:|")
    for r in resultats:
        ecart = 100 * (r["duree_tournees_min"] - ref["duree_tournees_min"]) / ref["duree_tournees_min"]
        print(f"| {r['methode']} | {r['silhouette']:.4f} | {r.get('compacite_med_m', 0):.0f} m "
              f"| {r['taille_max']} | {'oui' if r['faisable'] else 'NON'} "
              f"| {r['duree_tournees_min']:.1f} | {ecart:+.1f} % "
              f"| {r['temps_a_bord_moyen_min']:.1f} min | {r['temps_a_bord_p90_min']:.1f} min |")

    # ── Le pipeline de production complet, sur les deux distances ────────────
    ids = df["id"].to_numpy()
    print("\n## Pipeline de production complet (disperses DBSCAN -> Pareto -> LP)\n")
    print("| Distance | k choisi | Disperses | Silhouette (routiere) | Compacite med. "
          "| Flotte (min) | A bord moyen |")
    print("|---|--:|--:|--:|--:|--:|--:|")
    pipeline = {}
    for nom, D in (("routiere (production)", ROAD), ("euclidienne", EUC)):
        lab, res = pipeline_production(ids, XY, D)
        m = noter(lab, ROAD)
        m.update(metriques_tournees(lab, DUR, dur_depot))
        m["k_choisi"] = res["k"]
        m["n_disperses"] = res["n_disperses"]
        m["silhouette_rapportee_par_le_service"] = res["metrics"].get("silhouette")
        pipeline[nom] = m
        print(f"| {nom} | {res['k']} | {res['n_disperses']} | {m['silhouette']:.4f} "
              f"| {m.get('compacite_med_m', 0):.0f} m | {m['duree_tournees_min']:.1f} "
              f"| {m['temps_a_bord_moyen_min']:.1f} min |")

    # ── Variance : les ecarts de silhouette entre k voisins ont-ils un sens ? ─
    print("\n## Variance d'initialisation (10 graines, k-medoides routier)\n")
    print("| k | Silhouette moyenne | Ecart-type | Min | Max |")
    print("|--:|--:|--:|--:|--:|")
    variances = []
    for kk in (6, 7, 8, 9):
        v = variance_graines(ROAD, XY, kk, ROAD)
        variances.append(v)
        print(f"| {kk} | {v['silhouette_moy']:.4f} | {v['silhouette_ecart_type']:.4f} "
              f"| {v['silhouette_min']:.4f} | {v['silhouette_max']:.4f} |")

    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "ablation_distance.json"), "w", encoding="utf-8") as f:
        json.dump({"n": n, "k": k, "capacite": CAP, "projection": proj,
                   "arene": resultats, "pipeline_production": pipeline,
                   "variance_graines": variances}, f, indent=2, ensure_ascii=False)
    print(f"\n[MS6] -> {os.path.join(DATA, 'ablation_distance.json')}")


if __name__ == "__main__":
    main()
