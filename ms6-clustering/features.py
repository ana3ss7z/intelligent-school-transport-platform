"""
Préparation des descripteurs géographiques pour le clustering.

Principe clé (cf. notebook 1) : on ne fait PAS de StandardScaler(lat, lon) — cela déforme la
géométrie réelle à 33.9°N. On projette en mètres (UTM 30N / EPSG:32630 via pyproj, repli plan
tangent local) pour que la distance euclidienne ≈ distance au sol.
"""
import math
import logging

import numpy as np

from config import settings

logger = logging.getLogger(__name__)
EARTH_RADIUS_M = 6_371_000.0


def extraire_coords(eleves: list[dict]) -> tuple[list[int], np.ndarray]:
    """Retourne (ids, latlon[n,2]) en filtrant les élèves sans coordonnées."""
    ids, latlon = [], []
    for e in eleves:
        lat, lon = e.get("latitude"), e.get("longitude")
        if lat is not None and lon is not None:
            ids.append(e["id"])
            latlon.append([float(lat), float(lon)])
    return ids, np.asarray(latlon, dtype=float)


def projeter_metres(latlon: np.ndarray) -> tuple[np.ndarray, str]:
    """Projette (lat, lon) -> (x, y) mètres. UTM si pyproj dispo, sinon plan tangent local."""
    lat, lon = latlon[:, 0], latlon[:, 1]
    try:
        from pyproj import Transformer
        tr = Transformer.from_crs("EPSG:4326", f"EPSG:{settings.epsg_metric}", always_xy=True)
        x, y = tr.transform(lon, lat)
        return np.column_stack([x, y]), f"UTM EPSG:{settings.epsg_metric}"
    except Exception as exc:
        logger.warning("[MS6] pyproj indisponible (%s) — plan tangent local", exc)
        lat0, lon0 = lat.mean(), lon.mean()
        x = np.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
        y = np.radians(lat - lat0) * EARTH_RADIUS_M
        return np.column_stack([x, y]), "plan tangent local"


def matrice_haversine(latlon: np.ndarray) -> np.ndarray:
    """Matrice n×n des distances à vol d'oiseau (mètres) — repli si OSRM indisponible."""
    la = np.radians(latlon[:, 0])[:, None]
    lo = np.radians(latlon[:, 1])[:, None]
    dla, dlo = la - la.T, lo - lo.T
    a = np.sin(dla / 2) ** 2 + np.cos(la) * np.cos(la.T) * np.sin(dlo / 2) ** 2
    D = 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    np.fill_diagonal(D, 0.0)
    return D


def matrice_euclidienne(XY: np.ndarray) -> np.ndarray:
    """Matrice n×n des distances euclidiennes (mètres) dans l'espace projeté."""
    diff = XY[:, None, :] - XY[None, :, :]
    D = np.sqrt((diff ** 2).sum(axis=2))
    np.fill_diagonal(D, 0.0)
    return D
