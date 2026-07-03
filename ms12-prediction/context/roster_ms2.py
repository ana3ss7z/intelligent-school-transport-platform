"""
Occupation du bus en production — estimée depuis MS2 (EleveService).

À l'heure de départ, on ne connaît pas les montées réelles ; on les **estime** à partir du roster :
nombre d'élèves affectés au bus (MS2). On en déduit `taux_occupation` et une estimation simple des
montées/descentes par tronçon. Les valeurs **réelles** arriveront plus tard via l'app chauffeur (présence).
"""
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)
CAPACITE_BUS = 50


async def get_effectif_bus(bus_id: int) -> int:
    """Nombre d'élèves affectés à un bus (via MS2). 0 si indisponible."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{settings.ms2_url}/api/eleves")
            r.raise_for_status()
            eleves = r.json()
            return sum(1 for e in eleves if e.get("busId") == bus_id)
    except Exception as exc:
        logger.warning("[MS12] MS2 indisponible (%s) — effectif inconnu", exc)
        return 0


async def get_occupation(bus_id: int, moment: str, leg_id: int, n_arrets: int) -> tuple[dict, str]:
    """
    Estime (nb_montees, nb_descentes, taux_occupation) pour un tronçon.
    Modèle simple : matin = remplissage progressif ; soir = vidage progressif.
    Retourne (dict, source).
    """
    effectif = await get_effectif_bus(bus_id)
    if effectif <= 0:
        return {"nb_montees": 0, "nb_descentes": 0, "taux_occupation": 0.0}, "défaut (MS2 indispo)"

    par_arret = max(1, round(effectif / max(1, n_arrets)))
    if moment == "matin":
        montees, descentes = (par_arret if leg_id < n_arrets - 1 else 0), 0
        a_bord = min(effectif, par_arret * (leg_id + 1))
    else:
        montees, descentes = 0, (par_arret if leg_id > 0 else 0)
        a_bord = max(0, effectif - par_arret * leg_id)
    taux = round(min(1.0, a_bord / CAPACITE_BUS), 3)
    return {"nb_montees": montees, "nb_descentes": descentes, "taux_occupation": taux}, "roster MS2"
