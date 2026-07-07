"""
Solveur VRP — TSP par bus (dépôt = école) avec OR-Tools, + baseline « plus proche voisin ».

Le bus part de l'école (dépôt, index 0), ramasse tous ses élèves, revient à l'école.
On minimise la **durée totale** (matrice OSRM). La baseline gloutonne sert à mesurer le **gain**.
"""
import logging

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

logger = logging.getLogger(__name__)


def cout_tournee(order: list[int], M: list[list[float]]) -> float:
    """Somme des arcs le long d'un ordre de visite (order inclut le dépôt au début et à la fin)."""
    return sum(M[order[i]][order[i + 1]] for i in range(len(order) - 1))


def baseline_plus_proche(D: list[list[float]], depot: int = 0) -> list[int]:
    """Ordre glouton : à chaque étape, aller au nœud non visité le plus proche ; retour dépôt."""
    n = len(D)
    non_visites = set(range(n)) - {depot}
    order = [depot]
    cur = depot
    while non_visites:
        nxt = min(non_visites, key=lambda j: D[cur][j])
        order.append(nxt); non_visites.remove(nxt); cur = nxt
    order.append(depot)
    return order


def solve_tsp(D: list[list[float]], depot: int = 0, time_limit_s: int = 5) -> list[int]:
    """TSP OR-Tools : ordre optimal de visite (inclut le dépôt au début et à la fin)."""
    n = len(D)
    if n <= 1:
        return [depot]
    if n == 2:
        autre = 1 - depot
        return [depot, autre, depot]

    manager = pywrapcp.RoutingIndexManager(n, 1, depot)
    routing = pywrapcp.RoutingModel(manager)
    Dint = [[int(round(D[i][j])) for j in range(n)] for i in range(n)]

    def cb(a, b):
        return Dint[manager.IndexToNode(a)][manager.IndexToNode(b)]

    t = routing.RegisterTransitCallback(cb)
    routing.SetArcCostEvaluatorOfAllVehicles(t)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromSeconds(max(1, time_limit_s))

    sol = routing.SolveWithParameters(params)
    if sol is None:
        logger.warning("[MS5] OR-Tools sans solution — repli plus proche voisin")
        return baseline_plus_proche(D, depot)

    order, index = [], routing.Start(0)
    while not routing.IsEnd(index):
        order.append(manager.IndexToNode(index))
        index = sol.Value(routing.NextVar(index))
    order.append(manager.IndexToNode(index))   # retour au dépôt
    return order
