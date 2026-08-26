"""Client HTTP vers MS2-EleveService (élèves par groupe / tous), avec retry Tenacity."""
import logging

import httpx
from tenacity import (retry, stop_after_attempt, wait_exponential,
                      retry_if_exception_type)

from config import settings

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8),
       retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)))
async def get_all_eleves() -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Route INTERNE : /internal/eleves, hors de /api/eleves/** donc non routee
        # par la passerelle. GET /api/eleves exige desormais un JWT (defaut critique
        # n.2 de la recette du 26/08 : 301 eleves + domiciles GPS servis sans jeton).
        r = await client.get(f"{settings.ms2_url}/internal/eleves")
        r.raise_for_status()
        return r.json()


async def get_eleves_groupe(groupe_id: int) -> list[dict]:
    """Élèves d'un groupe. Filtré depuis /internal/eleves (route interne, comme MS6) —
    évite l'endpoint /groupe/{id} qui exige un JWT utilisateur que MS5 n'a pas."""
    eleves = await get_all_eleves()
    return [e for e in eleves if e.get("groupeId") == groupe_id]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8),
       retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)))
async def assigner_ordre_bulk(eleve_ordre: dict[int, int]) -> int:
    """Persiste l'ordre de passage des tournées via PUT /api/eleves/ordre/bulk (route interne)."""
    if not eleve_ordre:
        return 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(f"{settings.ms2_url}/api/eleves/ordre/bulk",
                             json={str(k): v for k, v in eleve_ordre.items()})
        r.raise_for_status()
        return r.json().get("updated", 0)
