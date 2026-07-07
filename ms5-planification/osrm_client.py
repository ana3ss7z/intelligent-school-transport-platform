"""
Client OSRM pour le VRP :
- `matrice()` : matrices n×n de durées (s) et distances (m) via /table (repli haversine si OSRM off) ;
- `geometrie()` : polyligne routière réelle passant par les arrêts dans l'ordre (via /route, GeoJSON).
"""
import math
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)
VITESSE_REPLI_KMH = 30.0
FACTEUR_ROUTIER = 1.4


def haversine_m(a, b) -> float:
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi = math.radians(b[0] - a[0]); dlmb = math.radians(b[1] - a[1])
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def _coords(latlon):
    return ";".join(f"{p[1]},{p[0]}" for p in latlon)


async def matrice(latlon: list[tuple]) -> tuple[list[list[float]], list[list[float]]]:
    """(durees_s, distances_m) n×n. Repli haversine si OSRM injoignable."""
    n = len(latlon)
    try:
        url = (f"{settings.osrm_url}/table/v1/driving/{_coords(latlon)}"
               f"?annotations=duration,distance")
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            j = r.json()
        dur = [[float(x) for x in row] for row in j["durations"]]
        dist = [[float(x) for x in row] for row in j["distances"]]
        return dur, dist
    except Exception as exc:
        logger.warning("[MS5] OSRM /table indisponible (%s) — repli vol d'oiseau", exc)
        dist = [[haversine_m(latlon[i], latlon[j]) * FACTEUR_ROUTIER for j in range(n)] for i in range(n)]
        dur = [[dist[i][j] / (VITESSE_REPLI_KMH * 1000 / 3600) for j in range(n)] for i in range(n)]
        return dur, dist


async def geometrie(latlon_ordre: list[tuple]) -> list[list[float]]:
    """Polyligne [[lat,lng]...] de l'itinéraire réel passant par les points dans l'ordre."""
    try:
        url = (f"{settings.osrm_url}/route/v1/driving/{_coords(latlon_ordre)}"
               f"?overview=full&geometries=geojson")
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            coords = r.json()["routes"][0]["geometry"]["coordinates"]
        return [[c[1], c[0]] for c in coords]
    except Exception as exc:
        logger.warning("[MS5] OSRM /route indisponible (%s) — polyligne = arrêts bruts", exc)
        return [[p[0], p[1]] for p in latlon_ordre]
