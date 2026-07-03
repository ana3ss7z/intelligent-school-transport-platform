"""
Météo en production — via Open-Meteo (GRATUIT, sans clé API).

Source : https://api.open-meteo.com/v1/forecast → champ `weather_code` (WMO) → catégorie du modèle
({ensoleille, nuageux, pluie, brouillard}). Repli sur une **climatologie saisonnière** si hors-ligne
ou si `WEATHER_PROVIDER=off`. Retourne (catégorie, source) pour la transparence.
"""
import logging
from datetime import date

import httpx

from config import settings

logger = logging.getLogger(__name__)


def _wmo_to_cat(code: int) -> str:
    """Code WMO Open-Meteo → catégorie météo du modèle."""
    if code == 0:
        return "ensoleille"
    if code in (1, 2, 3):
        return "nuageux"
    if code in (45, 48):
        return "brouillard"
    return "pluie"   # 51-67 bruine/pluie, 71-77 neige, 80-99 averses/orages


def _climatologie(mois: int) -> str:
    """Repli hors-ligne : catégorie la plus probable selon la saison (Meknès)."""
    if mois in (11, 12, 1, 2, 3):     # saison humide
        return "nuageux"
    return "ensoleille"


async def get_meteo(lat: float, lng: float, mois: int | None = None) -> tuple[str, str]:
    """(catégorie, source). Ne lève jamais d'exception."""
    mois = mois or date.today().month
    if settings.weather_provider != "open-meteo":
        return _climatologie(mois), "climatologie"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(settings.weather_url, params={
                "latitude": lat, "longitude": lng, "current": "weather_code"})
            r.raise_for_status()
            code = int(r.json()["current"]["weather_code"])
            return _wmo_to_cat(code), "open-meteo"
    except Exception as exc:
        logger.warning("[MS12] Open-Meteo indisponible (%s) — repli climatologie", exc)
        return _climatologie(mois), "climatologie (repli)"
