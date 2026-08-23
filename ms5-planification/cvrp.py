"""
CVRP global — affectation ET routage résolus ensemble, en un seul modèle OR-Tools.

À quoi ça sert ici : c'est le **point de comparaison** de l'architecture retenue en production.
MS5 décompose le problème — MS6 affecte les élèves aux bus sous contrainte de capacité, puis MS5
résout un TSP par bus (`vrp.py`). Cette décomposition est confortable, mais elle est *a priori*
sous-optimale : elle fige l'affectation avant de connaître le coût des tournées qui en découlent.

Le CVRP répond à la question « combien coûte cette décomposition ? » en résolvant les deux
décisions d'un bloc. Le résultat est instructif dans les deux sens :
  · s'il gagne nettement, on quantifie ce que la décomposition nous coûte ;
  · s'il gagne peu ou perd, c'est une **validation** de MS6→MS5 — parce que la décomposition de MS6
    n'est pas arbitraire, elle est géographiquement informée (k-médoïdes sur distance routière),
    là où le CVRP part à froid.

Ce module est **hors du chemin de production** : aucun endpoint ne l'appelle. Il sert au notebook
`notebooks/06_cvrp_benchmark.ipynb`.
"""
import logging
import time

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

logger = logging.getLogger(__name__)


def solve_cvrp(
    M: list[list[float]],
    n_vehicules: int,
    capacite: int,
    depot: int = 0,
    time_limit_s: int = 30,
    cout_fixe_vehicule: int = 0,
    demandes: list[int] | None = None,
) -> tuple[list[list[int]], bool]:
    """
    Résout un CVRP : `n_vehicules` partent du dépôt, desservent tous les nœuds, reviennent.

    `M` est la matrice de coûts (durées en secondes, comme le TSP de `vrp.py` — les deux approches
    doivent minimiser la **même** grandeur, sinon la comparaison ne veut rien dire).
    `demandes` vaut 1 par élève et 0 au dépôt par défaut : un élève = une place.

    `cout_fixe_vehicule` > 0 pénalise l'usage d'un bus. À 0 (défaut), le solveur utilise volontiers
    tous les véhicules disponibles — c'est normal en VRP, répartir raccourcit chaque boucle — et
    c'est ce qu'il faut pour comparer à parité avec MS6+TSP, qui utilise exactement `k` bus.
    Le mettre à une valeur élevée répond à une autre question : « combien de bus suffiraient ? ».

    Retourne `(routes, optimal_trouve)` où chaque route contient le dépôt au début et à la fin.
    Les routes vides (véhicule inutilisé) sont conservées telles quelles : `[depot, depot]`.
    """
    n = len(M)
    if n <= 1:
        return [[depot]], True
    if demandes is None:
        demandes = [0 if i == depot else 1 for i in range(n)]

    if sum(demandes) > n_vehicules * capacite:
        raise ValueError(
            f"Instance infaisable : {sum(demandes)} élèves pour "
            f"{n_vehicules} bus × {capacite} places"
        )

    manager = pywrapcp.RoutingIndexManager(n, n_vehicules, depot)
    routing = pywrapcp.RoutingModel(manager)

    # OR-Tools travaille en entiers : on arrondit la matrice une seule fois, exactement comme
    # `vrp.solve_tsp`, pour que les deux approches subissent la même perte de précision.
    Mint = [[int(round(M[i][j])) for j in range(n)] for i in range(n)]

    def cout_arc(a, b):
        return Mint[manager.IndexToNode(a)][manager.IndexToNode(b)]

    idx_cout = routing.RegisterTransitCallback(cout_arc)
    routing.SetArcCostEvaluatorOfAllVehicles(idx_cout)

    def demande(a):
        return demandes[manager.IndexToNode(a)]

    idx_demande = routing.RegisterUnaryTransitCallback(demande)
    routing.AddDimensionWithVehicleCapacity(
        idx_demande,
        0,                        # pas de marge : la capacité est une contrainte dure
        [capacite] * n_vehicules,
        True,                     # la charge démarre à zéro au dépôt
        "Capacite",
    )

    if cout_fixe_vehicule:
        routing.SetFixedCostOfAllVehicles(cout_fixe_vehicule)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromSeconds(max(1, time_limit_s))

    sol = routing.SolveWithParameters(params)
    if sol is None:
        logger.warning("[MS5] CVRP sans solution en %ss", time_limit_s)
        return [], False

    routes = []
    for v in range(n_vehicules):
        route, index = [], routing.Start(v)
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = sol.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))
        routes.append(route)
    return routes, True


def cout_routes(routes: list[list[int]], M: list[list[float]]) -> float:
    """Somme des arcs sur l'ensemble des routes (unité de `M`)."""
    return sum(
        M[r[i]][r[i + 1]] for r in routes for i in range(len(r) - 1)
    )


def charges(routes: list[list[int]], depot: int = 0) -> list[int]:
    """Nombre d'élèves par véhicule — sert à mesurer l'équilibrage entre bus."""
    return [len([x for x in r if x != depot]) for r in routes]


def bus_utilises(routes: list[list[int]], depot: int = 0) -> int:
    """Véhicules ayant au moins un arrêt (une route vide est `[depot, depot]`)."""
    return sum(1 for r in routes if any(x != depot for x in r))


def chronometre(fn, *args, **kwargs):
    """Exécute `fn` et renvoie `(resultat, duree_s)` — le temps de résolution fait partie du verdict."""
    t0 = time.perf_counter()
    res = fn(*args, **kwargs)
    return res, time.perf_counter() - t0
