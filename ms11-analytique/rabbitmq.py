"""
Consumer RabbitMQ MS11 (intégration G3) — monitor d'anomalies GPS live.
Consomme `gps.bus.updated` (MS3) et applique les règles instantanées de `live_monitor`.
Mode dégradé silencieux si RabbitMQ est indisponible.
"""
from __future__ import annotations

import json
import logging

import aio_pika

from config import settings
from live_monitor import observer, set_route, clear_route

logger = logging.getLogger(__name__)

_exchange: aio_pika.Exchange | None = None


async def _publier_anomalie(a: dict) -> None:
    """Publie anomalie.detectee → MS4 (canal admin D1). content_type text/plain (compat MS4)."""
    if _exchange is None:
        return
    try:
        await _exchange.publish(
            aio_pika.Message(body=json.dumps(a).encode(), content_type="text/plain"),
            routing_key="anomalie.detectee")
    except Exception as exc:
        logger.warning("[MS11] Publication anomalie.detectee échouée : %s", exc)


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
        vitesse = node.get("vitesse")   # km/h si fourni par MS3, sinon None (dérivé des positions)
        try:
            detections = observer(int(bus_id), float(lat), float(lng),
                                  float(vitesse) if vitesse is not None else None)
        except Exception as exc:
            logger.warning("[MS11] Monitor GPS erreur bus %s : %s", bus_id, exc)
            return
        for a in detections:
            logger.warning("[MS11] ⚠️ Anomalie live %s — bus %s (%s)",
                           a["type"], a["busId"], {k: v for k, v in a.items() if k not in ("busId", "type")})
            await _publier_anomalie(a)                  # canal admin (D1)


async def _on_trajet(message: aio_pika.IncomingMessage) -> None:
    """Fige (démarrage) ou purge (fin) la route de référence d'un bus pour la déviation."""
    async with message.process():
        try:
            node = json.loads(message.body.decode())
        except Exception:
            return
        bus_id = node.get("busId")
        statut = node.get("statut", "")
        if bus_id is None:
            return
        try:
            bus_id = int(bus_id)
        except Exception:
            return
        if statut == "EN_COURS":
            geo = node.get("geometrie")
            pts: list[tuple[float, float]] = []
            if geo:
                try:
                    raw = json.loads(geo) if isinstance(geo, str) else geo
                    pts = [(float(p[0]), float(p[1])) for p in raw if p and len(p) >= 2]
                except Exception as exc:
                    logger.warning("[MS11] Géométrie de trajet illisible (bus %s) : %s", bus_id, exc)
            if pts:
                set_route(bus_id, pts)
                logger.info("[MS11] Route figée pour bus %s (%d points) → surveillance déviation active", bus_id, len(pts))
            else:
                logger.info("[MS11] Trajet démarré bus %s sans géométrie → déviation inactive", bus_id)
        else:  # TERMINE (ou autre)
            clear_route(bus_id)
            logger.info("[MS11] Route purgée pour bus %s → surveillance déviation arrêtée", bus_id)


async def start_consumer() -> None:
    global _exchange
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        _exchange = await channel.declare_exchange(
            settings.exchange_name, aio_pika.ExchangeType.TOPIC, durable=True)
        exchange = _exchange
        queue = await channel.declare_queue("ms11.gps.queue", durable=True)
        await queue.bind(exchange, routing_key="gps.bus.updated")
        await queue.consume(_on_message)

        # Cycle de vie des trajets (MS1) → fige/purge la route de référence (déviation UC-8)
        tq = await channel.declare_queue("ms11.trajet.queue", durable=True)
        await tq.bind(exchange, routing_key="trajet.demarre")
        await tq.bind(exchange, routing_key="trajet.termine")
        await tq.consume(_on_trajet)

        logger.info("[MS11] Consumer RabbitMQ démarré (gps.bus.updated + trajet.* → monitor anomalies live)")
    except Exception as exc:
        logger.error("[MS11] RabbitMQ inaccessible : %s — monitor GPS live désactivé", exc)
