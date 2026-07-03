"""
Historique des trajets — source de la feature `duree_moyenne_historique`.

En production, cette feature = moyenne des durées **réalisées** des jours passés (même circuit/moment/tronçon).
- Au démarrage (cold-start), aucun historique réel → repli sur la durée OSRM de base.
- On peut **bootstrapper** l'historique avec le dataset d'entraînement (`HISTORY_PATH=data/eta_dataset.csv`),
  puis l'enrichir avec les trajets réels au fil du temps (`enregistrer_trajet`).
"""
import logging
import os

import pandas as pd

from config import settings

logger = logging.getLogger(__name__)
_cache: pd.DataFrame | None = None


def _charger() -> pd.DataFrame | None:
    """Historique réel s'il existe, sinon bootstrap sur le dataset d'entraînement (lecture seule)."""
    global _cache
    if _cache is not None:
        return _cache
    for path in (settings.history_path, settings.dataset_path):   # réel prioritaire, sinon bootstrap
        if path and os.path.exists(path):
            try:
                _cache = pd.read_csv(path, usecols=lambda c: c in (
                    "circuit_id", "moment", "leg_id", "duree_reelle_min"))
                return _cache
            except Exception as exc:
                logger.warning("[MS12] Historique illisible (%s)", exc)
    return None


def get_duree_moyenne_historique(circuit_id, moment, leg_id, duree_base_s: float) -> tuple[float, str]:
    """(durée moyenne historique en secondes, source). Cold-start → durée OSRM de base."""
    df = _charger()
    if df is not None and circuit_id is not None and leg_id is not None:
        sub = df[(df["circuit_id"] == int(circuit_id)) &
                 (df["moment"] == moment) &
                 (df["leg_id"] == int(leg_id))]
        if len(sub):
            return float(sub["duree_reelle_min"].mean() * 60.0), "historique"
    return float(duree_base_s), "cold-start (OSRM)"


def enregistrer_trajet(circuit_id, moment, leg_id, duree_reelle_min: float):
    """Ajoute un trajet réalisé à l'historique (append CSV) — alimente la feature au fil du temps."""
    global _cache
    path = settings.history_path
    ligne = pd.DataFrame([{"circuit_id": circuit_id, "moment": moment,
                           "leg_id": leg_id, "duree_reelle_min": duree_reelle_min}])
    header = not os.path.exists(path)
    ligne.to_csv(path, mode="a", header=header, index=False)
    _cache = None  # invalide le cache
