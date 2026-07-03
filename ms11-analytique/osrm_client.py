"""Client OSRM léger — durée/distance de base d'un tronçon (repli vol d'oiseau)."""
import math
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)
VITESSE_REPLI_KMH = 30.0
FACTEUR_ROUTIER = 1.4


def _haversine_m(o_lat, o_lng, d_lat, d_lng):
    R = 6371000.0
    p1, p2 = math.radians(o_lat), math.radians(d_lat)
    a = (math.sin(math.radians(d_lat - o_lat) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d_lng - o_lng) / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


async def route_async(o_lat, o_lng, d_lat, d_lng) -> tuple[float, float]:
    """(durée_s, distance_m). Repli haversine si OSRM injoignable."""
    url = f"{settings.osrm_url}/route/v1/driving/{o_lng},{o_lat};{d_lng},{d_lat}?overview=false"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            route = r.json()["routes"][0]
            return float(route["duration"]), float(route["distance"])
    except Exception as exc:
        logger.warning("[MS11] OSRM indisponible (%s) — repli vol d'oiseau", exc)
        dist = _haversine_m(o_lat, o_lng, d_lat, d_lng) * FACTEUR_ROUTIER
        return dist / (VITESSE_REPLI_KMH * 1000 / 3600), dist
