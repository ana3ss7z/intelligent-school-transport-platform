"""
Trafic en production — heuristique horaire (GRATUIT, sans API).

Il n'existe pas d'API de trafic temps réel gratuite *sans clé*. On estime donc le niveau de trafic
à partir de l'heure : heures de pointe (7-9h / 17-19h) = trafic dense, transitions = modéré, sinon fluide.
Le week-end, le trafic est allégé. Retourne (catégorie, source).

Option : si `TRAFFIC_PROVIDER=tomtom` et `TOMTOM_KEY` fourni, on pourrait interroger l'API TomTom
(free-tier 2500 req/jour). Non activé par défaut → repli heuristique.
"""
import logging

from config import settings

logger = logging.getLogger(__name__)


def _heuristique(heure: float, jour_semaine: int) -> str:
    weekend = jour_semaine >= 5
    pointe = (7.0 <= heure <= 9.0) or (17.0 <= heure <= 19.0)
    proche = (6.5 <= heure < 7.0) or (9.0 < heure <= 10.0) or \
             (16.0 <= heure < 17.0) or (19.0 < heure <= 20.0)
    if weekend:
        return "modere" if pointe else "fluide"
    if pointe:
        return "dense"
    if proche:
        return "modere"
    return "fluide"


def get_trafic(heure: float, jour_semaine: int) -> tuple[str, str]:
    """(catégorie, source). Heuristique horaire (défaut) ; TomTom si configuré."""
    if settings.traffic_provider == "tomtom" and settings.tomtom_key:
        # Placeholder : intégration TomTom Flow possible ici (nécessite clé + réseau).
        logger.info("[MS12] TOMTOM demandé mais intégration non activée — repli heuristique")
    return _heuristique(heure, jour_semaine), "heuristique"
