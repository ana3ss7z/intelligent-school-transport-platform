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
from live_monitor import observer

logger = logging.getLogger(__name__)


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


async def start_consumer() -> None:
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        exchange = await channel.declare_exchange(
            settings.exchange_name, aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue("ms11.gps.queue", durable=True)
        await queue.bind(exchange, routing_key="gps.bus.updated")
        await queue.consume(_on_message)
        logger.info("[MS11] Consumer RabbitMQ démarré (gps.bus.updated → monitor anomalies live)")
    except Exception as exc:
        logger.error("[MS11] RabbitMQ inaccessible : %s — monitor GPS live désactivé", exc)
