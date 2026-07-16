"""
Monitor d'anomalies GPS INSTANTANÉES (MS11) — intégration G3.

Complémentaire du détecteur ML (Isolation Forest), qui score des *trajets complets* a-posteriori.
Ici on traite les anomalies **instantanées** du flux GPS (UC-8 : « arrêt prolongé, vitesse anormale »),
calculables à partir des positions successives — ce qu'un modèle trajet ne sait pas faire sur un ping.

État par bus, règles simples :
- ARRET_PROLONGE : le bus reste quasi immobile (< arret_rayon_m) plus de seuil_arret_min.
- VITESSE_EXCESSIVE : vitesse (payload ou calculée) > seuil_vitesse_kmh.

Sortie : buffer mémoire (exposé par GET /api/analytique/live) + logs. Pas d'événement sans consommateur.
"""
from __future__ import annotations

import math
import time
from collections import deque
from datetime import datetime, timezone

from config import settings

# Buffer partagé des dernières anomalies live (lu par l'endpoint /live)
anomalies_live: deque = deque(maxlen=100)

_state: dict[int, dict] = {}          # busId -> {last_pos, last_ts, immobile_depuis, last_alert}
_ALERT_COOLDOWN_S = 120.0             # une alerte par type et par bus au plus toutes les 2 min


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi = math.radians(b[0] - a[0]); dl = math.radians(b[1] - a[1])
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def _emit(bus_id: int, type_anom: str, detail: dict) -> dict:
    entry = {"busId": bus_id, "type": type_anom,
             "timestamp": datetime.now(timezone.utc).isoformat(), **detail}
    anomalies_live.appendleft(entry)
    return entry


def observer(bus_id: int, lat: float, lng: float,
             vitesse_kmh: float | None, ts: float | None = None) -> list[dict]:
    """Traite une position GPS ; retourne la liste des anomalies déclenchées (souvent vide)."""
    now = ts if ts is not None else time.time()
    pos = (lat, lng)
    st = _state.get(bus_id)
    detections: list[dict] = []

    if st is None:
        _state[bus_id] = {"last_pos": pos, "last_ts": now, "immobile_depuis": now, "last_alert": {}}
        return detections

    dt = max(1e-6, now - st["last_ts"])
    dist = _haversine_m(st["last_pos"], pos)

    # Vitesse : payload si fourni, sinon dérivée des positions
    v = vitesse_kmh if vitesse_kmh is not None else (dist / dt) * 3.6

    def _cooldown_ok(kind: str) -> bool:
        return now - st["last_alert"].get(kind, 0.0) >= _ALERT_COOLDOWN_S

    # ── Vitesse excessive ──
    if v > settings.seuil_vitesse_kmh and _cooldown_ok("VITESSE_EXCESSIVE"):
        st["last_alert"]["VITESSE_EXCESSIVE"] = now
        detections.append(_emit(bus_id, "VITESSE_EXCESSIVE",
                                {"vitesse_kmh": round(v, 1), "seuil": settings.seuil_vitesse_kmh,
                                 "niveau": "critique"}))

    # ── Arrêt prolongé ──
    if dist < settings.arret_rayon_m:
        immobile_s = now - st["immobile_depuis"]
        if immobile_s > settings.seuil_arret_min * 60.0 and _cooldown_ok("ARRET_PROLONGE"):
            st["last_alert"]["ARRET_PROLONGE"] = now
            detections.append(_emit(bus_id, "ARRET_PROLONGE",
                                    {"immobile_min": round(immobile_s / 60.0, 1),
                                     "seuil_min": settings.seuil_arret_min, "niveau": "suspect"}))
    else:
        st["immobile_depuis"] = now   # le bus a bougé → on réarme le compteur d'immobilité

    st["last_pos"] = pos
    st["last_ts"] = now
    return detections
