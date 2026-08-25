"""
Monitor d'anomalies GPS INSTANTANÉES (MS11) — intégration G3.

Complémentaire du détecteur ML (Isolation Forest), qui score des *trajets complets* a-posteriori.
Ici on traite les anomalies **instantanées** du flux GPS (UC-8 : « arrêt prolongé, vitesse anormale »),
calculables à partir des positions successives — ce qu'un modèle trajet ne sait pas faire sur un ping.

État par bus, règles simples :
- ARRET_PROLONGE : le bus reste quasi immobile (< arret_rayon_m) plus de seuil_arret_min.
- VITESSE_EXCESSIVE : vitesse (payload ou calculée) > seuil_vitesse_kmh.
- DEVIATION_ITINERAIRE : la position s'écarte de plus de seuil_deviation_m de la tournée planifiée
  (route figée au démarrage du trajet par MS1, cf. set_route/clear_route). Actif uniquement pendant un trajet.

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

_state: dict[int, dict] = {}          # busId -> {last_pos, last_ts, immobile_depuis, last_alert, hors_couloir}
_routes: dict[int, list[tuple[float, float]]] = {}   # busId -> tournée planifiée [(lat,lng),…] (déviation)
_ALERT_COOLDOWN_S = 120.0             # une alerte par type et par bus au plus toutes les 2 min


def set_route(bus_id: int, pts: list[tuple[float, float]]) -> None:
    """Fige la route de référence d'un bus (appelé au démarrage d'un trajet)."""
    if pts:
        _routes[bus_id] = pts


def clear_route(bus_id: int) -> None:
    """Purge la route de référence (appelé à la fin du trajet) + réarme le compteur de déviation."""
    _routes.pop(bus_id, None)
    if bus_id in _state:
        _state[bus_id]["hors_couloir"] = 0


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi = math.radians(b[0] - a[0]); dl = math.radians(b[1] - a[1])
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def _dist_point_polyline_m(p: tuple[float, float], pts: list[tuple[float, float]]) -> float:
    """Distance min (m) entre un point et une polyligne, via projection équirectangulaire locale.

    On projette lat/lng en mètres autour du point (x = R·Δlng·cos(lat), y = R·Δlat) puis on calcule
    la distance point→segment classique. Suffisant aux échelles urbaines (couloir de quelques centaines de m)."""
    if not pts:
        return 0.0
    if len(pts) == 1:
        return _haversine_m(p, pts[0])
    R = 6371000.0
    lat0 = math.radians(p[0])
    cos0 = math.cos(lat0)

    def xy(q: tuple[float, float]) -> tuple[float, float]:
        return (R * math.radians(q[1] - p[1]) * cos0, R * math.radians(q[0] - p[0]))

    px, py = 0.0, 0.0   # le point est l'origine du repère local
    best = float("inf")
    prev = xy(pts[0])
    for k in range(1, len(pts)):
        cur = xy(pts[k])
        ax, ay = prev
        bx, by = cur
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        if seg2 <= 1e-9:
            d = math.hypot(px - ax, py - ay)
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
            projx, projy = ax + t * dx, ay + t * dy
            d = math.hypot(px - projx, py - projy)
        if d < best:
            best = d
        prev = cur
    return best


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
        _state[bus_id] = {"last_pos": pos, "last_ts": now, "immobile_depuis": now,
                          "last_alert": {}, "hors_couloir": 0, "vitesse_hors_seuil": 0}
        return detections

    dt = max(1e-6, now - st["last_ts"])
    dist = _haversine_m(st["last_pos"], pos)

    # Vitesse : payload si fourni, sinon dérivée des positions
    v = vitesse_kmh if vitesse_kmh is not None else (dist / dt) * 3.6

    def _cooldown_ok(kind: str) -> bool:
        return now - st["last_alert"].get(kind, 0.0) >= _ALERT_COOLDOWN_S

    # ── Vitesse excessive ──
    # Anti-rebond, calqué sur le compteur `hors_couloir` de la déviation. Il manquait ici :
    # la vitesse est soit relevée par le téléphone du chauffeur, soit dérivée de deux
    # positions successives — dans les deux cas un seul point aberrant (rebond GPS, tunnel,
    # reprise après perte de signal) produit une vitesse absurde. Sans compteur, ce point
    # unique déclenchait une alerte CRITIQUE. `vitesse_pings_consecutifs = 1` conserve le
    # comportement historique ; le porter à 2 exige une confirmation, comme pour la déviation.
    if v > settings.seuil_vitesse_kmh:
        st["vitesse_hors_seuil"] = st.get("vitesse_hors_seuil", 0) + 1
        if st["vitesse_hors_seuil"] >= settings.vitesse_pings_consecutifs and _cooldown_ok("VITESSE_EXCESSIVE"):
            st["last_alert"]["VITESSE_EXCESSIVE"] = now
            detections.append(_emit(bus_id, "VITESSE_EXCESSIVE",
                                    {"vitesse_kmh": round(v, 1), "seuil": settings.seuil_vitesse_kmh,
                                     "pings": st["vitesse_hors_seuil"], "niveau": "critique"}))
    else:
        st["vitesse_hors_seuil"] = 0      # repassé sous le seuil → on réarme

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

    # ── Déviation d'itinéraire (seulement si une route est figée = trajet en cours) ──
    route = _routes.get(bus_id)
    if route:
        ecart = _dist_point_polyline_m(pos, route)
        if ecart > settings.seuil_deviation_m:
            st["hors_couloir"] = st.get("hors_couloir", 0) + 1
            if st["hors_couloir"] >= settings.deviation_pings_consecutifs and _cooldown_ok("DEVIATION_ITINERAIRE"):
                st["last_alert"]["DEVIATION_ITINERAIRE"] = now
                detections.append(_emit(bus_id, "DEVIATION_ITINERAIRE",
                                        {"ecart_m": round(ecart, 1), "seuil": settings.seuil_deviation_m,
                                         "niveau": "critique"}))
        else:
            st["hors_couloir"] = 0        # rentré dans le couloir → on réarme

    st["last_pos"] = pos
    st["last_ts"] = now
    return detections
