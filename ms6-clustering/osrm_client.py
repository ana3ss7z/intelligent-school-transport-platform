"""
Client OSRM — matrice de distances ROUTIÈRES (réseau réel de Meknès).

OSRM limite /table à ~100 coordonnées par requête (max-table-size). On construit donc la matrice
n×n par blocs (50×50 = 100 coords/req) en parallèle. Les paires injoignables (-1/null) sont
comblées par la distance à vol d'oiseau. Matrice symétrisée (sens uniques) pour servir de métrique.
"""
import asyncio
import logging

import httpx
import numpy as np

from config import settings
from features import matrice_haversine

logger = logging.getLogger(__name__)
BLOCK = 50
MAX_CONCURRENCE = 6


async def matrice_routiere(latlon: np.ndarray, annotation: str = "distance") -> np.ndarray:
    """
    Matrice n×n des distances routières (mètres) via OSRM /table.
    annotation : "distance" (m) ou "duration" (s).
    Lève une exception si OSRM est injoignable (le caller bascule alors sur l'euclidien/haversine).
    """
    lat, lon = latlon[:, 0], latlon[:, 1]
    n = len(latlon)
    blocs = [list(range(i, min(i + BLOCK, n))) for i in range(0, n, BLOCK)]
    D = np.full((n, n), np.nan)
    sem = asyncio.Semaphore(MAX_CONCURRENCE)

    async with httpx.AsyncClient(timeout=60.0) as client:
        async def fetch(bi, bj):
            idx = bi + bj
            coords = ";".join(f"{lon[k]},{lat[k]}" for k in idx)
            s = ";".join(str(i) for i in range(len(bi)))
            d = ";".join(str(i) for i in range(len(bi), len(idx)))
            url = (f"{settings.osrm_url}/table/v1/driving/{coords}"
                   f"?annotations={annotation}&sources={s}&destinations={d}")
            async with sem:
                resp = await client.get(url)
            resp.raise_for_status()
            key = "distances" if annotation == "distance" else "durations"
            mat = np.array(resp.json()[key], dtype=float)
            for a, gi in enumerate(bi):
                for b, gj in enumerate(bj):
                    D[gi, gj] = mat[a, b]

        await asyncio.gather(*(fetch(bi, bj) for bi in blocs for bj in blocs))

    # Paires injoignables -> vol d'oiseau ; symétrisation ; diagonale nulle
    HV = matrice_haversine(latlon)
    bad = ~np.isfinite(D) | (D < 0)
    if bad.any():
        D[bad] = HV[bad]
        logger.info("[MS6] OSRM : %d paires injoignables comblées (vol d'oiseau)", int(bad.sum()))
    D = (D + D.T) / 2.0
    np.fill_diagonal(D, 0.0)
    return D
