"""
Consumer RabbitMQ MS6 — recalcule le clustering après chaque événement élève.
Utilise bulk update (1 requête HTTP) au lieu de N PATCH simultanés.
"""
import asyncio
import logging
import aio_pika
from config import settings
from clustering import run_kmeans
from ms2_client import assigner_groupes_bulk, get_all_eleves

logger = logging.getLogger(__name__)
_clustering_lock = asyncio.Lock()


async def _recalculer_et_ecrire():
    async with _clustering_lock:
        logger.info("[MS6] Recalcul clustering déclenché par RabbitMQ…")
        try:
            eleves = await get_all_eleves()
            if len(eleves) < 2:
                logger.warning("[MS6] Pas assez d'élèves (%d) — annulé", len(eleves))
                return

            result = run_kmeans(eleves)
            logger.info("[MS6] K-Means k=%d silhouette=%.4f", result.k, result.silhouette)

            # 1 seule requête HTTP bulk au lieu de N PATCH simultanés
            updated = await assigner_groupes_bulk(result.labels)
            logger.info("[MS6] %d/%d élèves mis à jour", updated, len(result.labels))

        except Exception as exc:
            logger.error("[MS6] Erreur clustering : %s", exc, exc_info=True)


async def _on_message(message: aio_pika.IncomingMessage):
    async with message.process():
        logger.info("[MS6] Message reçu — routing_key=%s", message.routing_key)
        if message.routing_key in ("eleve.created", "eleve.gps.updated", "eleve.deleted"):
            asyncio.create_task(_recalculer_et_ecrire())


async def start_consumer():
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)

        exchange = await channel.declare_exchange(
            settings.exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await channel.declare_queue("ms6.clustering.queue", durable=True)
        await queue.bind(exchange, routing_key="eleve.created")
        await queue.bind(exchange, routing_key="eleve.gps.updated")
        await queue.bind(exchange, routing_key="eleve.deleted")
        await queue.consume(_on_message)

        logger.info("[MS6] Consumer RabbitMQ démarré")
    except Exception as exc:
        logger.error("[MS6] RabbitMQ inaccessible : %s — mode dégradé", exc)