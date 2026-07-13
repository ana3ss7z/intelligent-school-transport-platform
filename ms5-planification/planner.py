"""
Orchestrateur de planification : groupe d'élèves → tournée optimale.
Étapes : arrêts (école + élèves) → matrice OSRM → OR-Tools (TSP) → ordre + distance/temps + géométrie + gain.
"""
import logging

from config import settings
from osrm_client import matrice, geometrie
from vrp import solve_tsp, baseline_plus_proche, cout_tournee

logger = logging.getLogger(__name__)


async def planifier(eleves: list[dict], sens: str = "matin") -> dict:
    """Calcule la tournée optimale d'un groupe.

    `sens` : matin (ramassage) | soir (dépose). **Même ordre de passage dans les deux sens** :
    la tournée optimale est un cycle (école→…→école). Sur une matrice symétrique, « même ordre »
    et « ordre inversé » coûtent la même chose ; mais sur la matrice OSRM **réelle (asymétrique)**
    l'ordre inversé n'est **pas ré-optimisé** et coûte souvent **davantage** (mesuré : ~2× sur un
    groupe réel de Meknès, cf. `verify_sens.py`). Garder le même ordre est donc **au moins aussi
    bon pour l'opérateur ET plus équitable** pour les élèves : le temps à bord matin + soir est le
    même pour tout le monde (l'élève ramassé en 1ᵉ le matin est déposé en 1ᵉ le soir), alors que
    l'inverser **pénalise deux fois** l'élève du bout de ligne. Le paramètre `sens` reste utile pour
    la sémantique (ramassage vs dépose) et l'affichage."""
    valides = [e for e in eleves if e.get("latitude") is not None and e.get("longitude") is not None]
    depot = (settings.ecole_lat, settings.ecole_lng)

    if len(valides) == 0:
        return {"n_arrets": 0, "ordre": [], "distance_m": 0.0, "duree_min": 0.0,
                "duree_base_min": 0.0, "gain_vs_baseline_%": 0.0, "geometrie": []}

    pts = [depot] + [(e["latitude"], e["longitude"]) for e in valides]
    dur, dist = await matrice(pts)

    order = solve_tsp(dur, depot=0, time_limit_s=settings.vrp_time_limit_s)
    base = baseline_plus_proche(dur, depot=0)

    duree_opt = cout_tournee(order, dur)
    duree_base = cout_tournee(base, dur)
    dist_opt = cout_tournee(order, dist)
    gain = round((duree_base - duree_opt) / duree_base * 100, 1) if duree_base > 0 else 0.0

    # indices de nœuds -> ids d'élèves (0 = école) ; ordre de passage
    # NB : même ordre matin et soir (voir docstring) — on n'inverse PAS le soir.
    passage = [i for i in order if i != 0]
    ordre_eleves = [valides[i - 1]["id"] for i in passage]

    latlon_order = [depot] + [(valides[i - 1]["latitude"], valides[i - 1]["longitude"]) for i in passage] + [depot]
    geom = await geometrie(latlon_order)

    return {
        "sens": sens,
        "n_arrets": len(valides),
        "ordre": ordre_eleves,
        "distance_m": round(dist_opt, 1),
        "duree_min": round(duree_opt / 60.0, 2),
        "duree_base_min": round(duree_base / 60.0, 2),
        "gain_vs_baseline_%": gain,
        "geometrie": geom,
    }
