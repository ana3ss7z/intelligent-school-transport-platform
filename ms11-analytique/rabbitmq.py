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


# État du consumer, exposé par /health et /live. Sans lui, une surveillance morte est
# indiscernable d'une surveillance qui n'a rien à signaler : /live répond 200 {"n": 0}
# dans les deux cas. C'est ce qui s'est produit le 27/08 — MS11 tournait, répondait, et
# n'observait plus rien depuis un redémarrage où RabbitMQ n'était pas encore prêt.
etat_consumer: dict = {"connecte": False, "tentatives": 0, "derniere_erreur": None,
                       "depuis": None}


async def start_consumer() -> None:
    """Démarre le monitor live, en RÉESSAYANT jusqu'à y parvenir.

    `connect_robust` reconnecte tout seul une connexion **déjà établie**, mais ne fait rien
    si la toute première tentative échoue. Or les 13 services démarrent ensemble : MS11 peut
    très bien se présenter avant que RabbitMQ n'accepte les connexions. La version précédente
    attrapait l'exception, écrivait une ligne de journal, et laissait le service tourner
    **sans aucune surveillance** — définitivement, jusqu'au prochain redémarrage manuel.
    """
    import asyncio as _asyncio
    attente = 2.0
    while True:
        try:
            await _demarrer_une_fois()
            return
        except Exception as exc:
            etat_consumer["tentatives"] += 1
            etat_consumer["derniere_erreur"] = str(exc)
            etat_consumer["connecte"] = False
            logger.error("[MS11] RabbitMQ inaccessible (essai %d) : %s — nouvelle tentative dans %.0f s",
                         etat_consumer["tentatives"], exc, attente)
            await _asyncio.sleep(attente)
            attente = min(attente * 2, 30.0)


async def _demarrer_une_fois() -> None:
    global _exchange
    if True:
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

        from datetime import datetime, timezone
        etat_consumer.update({"connecte": True, "derniere_erreur": None,
                              "depuis": datetime.now(timezone.utc).isoformat()})
        logger.info("[MS11] Consumer RabbitMQ démarré (gps.bus.updated + trajet.* → monitor anomalies live)")
