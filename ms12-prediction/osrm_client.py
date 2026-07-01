"""
Client OSRM — durée & distance routières point-à-point (réseau réel de Meknès).

- `route_sync()` : version synchrone (utilisée par le générateur de dataset).
- `route_async()` : version async (utilisée par le service FastAPI).
Repli à vol d'oiseau (haversine × 1.4, ~30 km/h) si OSRM est injoignable → le pipeline reste exécutable.
"""
import math
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

VITESSE_REPLI_KMH = 30.0
FACTEUR_ROUTIER = 1.4      # la route ≈ 1.4× la distance à vol d'oiseau


def haversine_m(o_lat, o_lng, d_lat, d_lng) -> float:
    R = 6371000.0
    p1, p2 = math.radians(o_lat), math.radians(d_lat)
    dphi = math.radians(d_lat - o_lat)
    dlmb = math.radians(d_lng - o_lng)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _repli(o_lat, o_lng, d_lat, d_lng) -> tuple[float, float]:
    dist = haversine_m(o_lat, o_lng, d_lat, d_lng) * FACTEUR_ROUTIER
    dur = dist / (VITESSE_REPLI_KMH * 1000 / 3600)   # secondes
    return dur, dist


def _url(o_lat, o_lng, d_lat, d_lng) -> str:
    return (f"{settings.osrm_url}/route/v1/driving/"
            f"{o_lng},{o_lat};{d_lng},{d_lat}?overview=false")


def route_sync(o_lat, o_lng, d_lat, d_lng) -> tuple[float, float]:
    """(durée_s, distance_m). Repli haversine si OSRM off. Jamais d'exception."""
    try:
        r = httpx.get(_url(o_lat, o_lng, d_lat, d_lng), timeout=15.0)
        r.raise_for_status()
        route = r.json()["routes"][0]
        return float(route["duration"]), float(route["distance"])
    except Exception as exc:
        logger.warning("[MS12] OSRM indisponible (%s) — repli vol d'oiseau", exc)
        return _repli(o_lat, o_lng, d_lat, d_lng)


async def route_async(o_lat, o_lng, d_lat, d_lng) -> tuple[float, float]:
    """Version async pour le service. Repli haversine si OSRM off."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(_url(o_lat, o_lng, d_lat, d_lng))
            r.raise_for_status()
            route = r.json()["routes"][0]
            return float(route["duration"]), float(route["distance"])
    except Exception as exc:
        logger.warning("[MS12] OSRM indisponible (%s) — repli vol d'oiseau", exc)
        return _repli(o_lat, o_lng, d_lat, d_lng)
