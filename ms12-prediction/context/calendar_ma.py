"""
Calendrier scolaire marocain — source des features `ramadan` et `jour_souk`, et des jours d'école.

En production, ces variables sont **calculées à partir de la date** (aucune API nécessaire) :
- Ramadan : fenêtres annuelles (dates approximatives, à affiner chaque année).
- Souk : jour de marché hebdomadaire (mercredi à Meknès) → congestion locale.
- Jours d'école : hors week-ends, vacances scolaires et jours fériés (pas de service ces jours-là).
"""
from datetime import date, timedelta

# Fenêtres de Ramadan (approximatives — à mettre à jour chaque année)
RAMADAN_WINDOWS = {
    2025: (date(2025, 3, 1), date(2025, 3, 30)),
    2026: (date(2026, 2, 18), date(2026, 3, 19)),
    2027: (date(2027, 2, 8), date(2027, 3, 9)),
}

# Vacances scolaires (blocs exclus du service) et jours fériés marocains
VACANCES = [
    (date(2025, 12, 20), date(2026, 1, 4)),
    (date(2026, 4, 5), date(2026, 4, 19)),
]
FERIES = {
    date(2025, 11, 6), date(2025, 11, 18), date(2026, 1, 1),
    date(2026, 1, 11), date(2026, 5, 1),
}

SOUK_WEEKDAY = 2  # mercredi


def _in_ranges(d: date, ranges) -> bool:
    return any(a <= d <= b for a, b in ranges)


def est_ramadan(d: date) -> int:
    w = RAMADAN_WINDOWS.get(d.year)
    return int(bool(w) and w[0] <= d <= w[1])


def jour_souk(d: date) -> int:
    return int(d.weekday() == SOUK_WEEKDAY)


def est_ferie(d: date) -> bool:
    return d in FERIES


def est_vacances(d: date) -> bool:
    return _in_ranges(d, VACANCES)


def est_jour_ecole(d: date) -> bool:
    """Lun–ven, hors vacances et fériés."""
    return d.weekday() < 5 and not est_vacances(d) and not est_ferie(d)


def jours_ecole(debut: date, n: int) -> list[date]:
    """n premiers jours d'école à partir de `debut`."""
    jours, d = [], debut
    while len(jours) < n:
        if est_jour_ecole(d):
            jours.append(d)
        d += timedelta(days=1)
    return jours
