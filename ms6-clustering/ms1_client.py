"""
Client HTTP vers MS1-BusService — récupère les capacités de la flotte active.
Calqué sur ms2_client (httpx + Tenacity). Sert à dériver le nombre de bus / la capacité.
"""
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=1, max=6),
       retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)))
async def get_bus_actifs() -> list[dict]:
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(f"{settings.ms1_url}/api/bus")
        resp.raise_for_status()
        bus = resp.json()
    return [b for b in bus if str(b.get("statut", "")).upper() == "ACTIF"]


async def get_capacites() -> list[int]:
    """Capacités des bus actifs ; liste vide si MS1 indisponible (le caller utilise un défaut)."""
    try:
        bus = await get_bus_actifs()
        return [int(b["capacite"]) for b in bus if b.get("capacite")]
    except Exception as exc:
        logger.warning("[MS6] MS1 indisponible (%s) — capacité par défaut utilisée", exc)
        return []
