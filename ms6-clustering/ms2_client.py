"""
Client HTTP vers MS2-EleveService.
- Bulk update avec retry automatique (Tenacity)
- 3 essais max : attend 2s, 4s, 8s entre chaque
"""
import logging
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from config import settings

logger = logging.getLogger(__name__)
MS2_BASE = settings.ms2_url


async def get_all_eleves() -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{MS2_BASE}/api/eleves")
        resp.raise_for_status()
        return resp.json()


async def get_eleves_sans_groupe() -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{MS2_BASE}/api/eleves/sans-groupe")
        resp.raise_for_status()
        return resp.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def assigner_groupes_bulk(labels: dict[int, int]) -> int:
    """
    PUT /api/eleves/groupes/bulk — 1 seule requête pour N élèves.
    Retry automatique si MS2 est temporairement indisponible.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.put(
            f"{MS2_BASE}/api/eleves/groupes/bulk",
            json={str(k): v for k, v in labels.items()},
        )
        resp.raise_for_status()
        updated = resp.json().get("updated", 0)
        logger.info("[MS6] Bulk update OK — %d élèves mis à jour", updated)
        return updated


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def assigner_bus_bulk(eleve_bus: dict[int, int]) -> int:
    """PUT /api/eleves/bus/bulk — propage busId (liaison groupe↔bus) en 1 requête."""
    if not eleve_bus:
        return 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.put(
            f"{MS2_BASE}/api/eleves/bus/bulk",
            json={str(k): v for k, v in eleve_bus.items()},
        )
        resp.raise_for_status()
        updated = resp.json().get("updated", 0)
        logger.info("[MS6] Bulk busId OK — %d élèves liés à un bus", updated)
        return updated