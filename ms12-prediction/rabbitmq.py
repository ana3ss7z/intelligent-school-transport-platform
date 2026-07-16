"""
Pipeline ETA temps réel (intégration G1) — MS12.

Consomme les positions GPS des bus publiées par MS3 (`gps.bus.updated`), calcule l'ETA d'arrivée
à l'école avec le modèle de prédiction, et — dès que l'ETA passe sous le seuil (par défaut 10 min) —
publie `eta.bus.arriving` que MS4 relaie en notification push aux parents (UC-4 « 10 min avant l'arrivée »).

Garde-fous :
- **throttle** par bus (on ne recalcule pas l'ETA à chaque tick GPS) ;
- **cooldown** d'alerte par bus (on n'alerte qu'une fois par trajet, pas à chaque position).

Limite assumée : l'alerte porte sur l'arrivée à l'**école** (destination unique connue). L'ETA par
**arrêt élève** nécessiterait la tournée persistée (intégration G2 — MS5) et le suivi de présence (G5).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime

import aio_pika

from config import settings

logger = logging.getLogger(__name__)

_exchange: aio_pika.Exchange | None = None
_last_check: dict[int, float] = {}   # busId -> timestamp du dernier calcul d'ETA
_alerted: dict[int, float] = {}      # busId -> timestamp de la dernière alerte envoyée


async def _compute_and_maybe_alert(bus_id: int, lat: float, lng: float) -> None:
    """Calcule l'ETA bus→école ; publie eta.bus.arriving si sous le seuil (avec cooldown)."""
    # Import différé : évite l'import circulaire (main importe start_consumer).
    from main import predict, PredictRequest

    now_dt = datetime.now()
    heure = now_dt.hour + now_dt.minute / 60.0
    moment = "matin" if heure < 12 else "soir"
    try:
        res = await predict(PredictRequest(
            bus_lat=lat, bus_lng=lng,
            dest_lat=settings.ecole_lat, dest_lng=settings.ecole_lng,
            moment=moment, heure_depart=heure, bus_id=bus_id, auto_context=True,
        ))
    except Exception as exc:  # modèle absent, OSRM indispo, etc. → on ignore ce tick
        logger.warning("[MS12] ETA non calculable pour le bus %s : %s", bus_id, exc)
        return

    eta = float(res["eta_minutes"])
    if not (0 < eta <= settings.eta_alert_min):
        return  # trop loin (ou déjà arrivé) → pas d'alerte

    now = time.time()
    if now - _alerted.get(bus_id, 0.0) < settings.eta_alert_cooldown_s:
        return  # déjà alerté récemment pour ce bus
    _alerted[bus_id] = now

    payload = {
        "busId": bus_id,
        "eta_min": round(eta, 1),
        "distance_m": res.get("distance_routiere_m"),
        "heure_arrivee_estimee": res.get("heure_arrivee_estimee"),
    }
    if _exchange is None:
        logger.warning("[MS12] Exchange non initialisé — alerte non publiée")
        return
    # content_type text/plain : les listeners MS4 (@RabbitListener String) lisent le corps brut
    # via objectMapper.readTree — un content_type application/json ferait échouer le convertisseur.
    await _exchange.publish(
        aio_pika.Message(body=json.dumps(payload).encode(),
                         content_type="text/plain"),
        routing_key="eta.bus.arriving",
    )
    logger.info("[MS12] 🔔 eta.bus.arriving — bus %s arrive dans %.1f min (%s)",
                bus_id, eta, res.get("heure_arrivee_estimee"))


async def _on_message(message: aio_pika.IncomingMessage) -> None:
    async with message.process():
        try:
            node = json.loads(message.body.decode())
        except Exception:
            return
        if node.get("cibleType") != "BUS":
            return
        bus_id, lat, lng = node.get("cibleId"), node.get("latitude"), node.get("longitude")
        if bus_id is None or lat is None or lng is None:
            return
        bus_id = int(bus_id)

        now = time.time()
        if now - _last_check.get(bus_id, 0.0) < settings.eta_check_throttle_s:
            return  # throttle : pas plus d'un calcul toutes les N secondes par bus
        _last_check[bus_id] = now
        asyncio.create_task(_compute_and_maybe_alert(bus_id, float(lat), float(lng)))


async def start_consumer() -> None:
    """Démarre le consumer gps.bus.updated (mode dégradé silencieux si RabbitMQ indisponible)."""
    global _exchange
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        _exchange = await channel.declare_exchange(
            settings.exchange_name, aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue("ms12.eta.queue", durable=True)
        await queue.bind(_exchange, routing_key="gps.bus.updated")
        await queue.consume(_on_message)
        logger.info("[MS12] Consumer RabbitMQ démarré (gps.bus.updated → ETA → eta.bus.arriving)")
    except Exception as exc:
        logger.error("[MS12] RabbitMQ inaccessible : %s — pipeline ETA temps réel désactivé", exc)
