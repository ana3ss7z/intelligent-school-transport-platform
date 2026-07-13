"""
Consumer RabbitMQ MS6 — recalcule le clustering après chaque événement élève.
Utilise bulk update (1 requête HTTP) au lieu de N PATCH simultanés.
"""
import asyncio
import logging
import aio_pika
from config import settings
from clustering import production_clustering
from ms2_client import assigner_groupes_bulk, get_all_eleves
from quality import maybe_maj_baseline

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

            # Recalcul auto : stratégie de production (distance routière optionnelle via .env)
            result = await production_clustering(eleves, use_road=settings.use_road_for_auto)
            logger.info("[MS6] Recalcul k=%d silhouette=%s (%s)",
                        result.k, result.silhouette, result.extra.get("distance"))

            # 1 seule requête HTTP bulk au lieu de N PATCH simultanés
            updated = await assigner_groupes_bulk(result.labels)
            logger.info("[MS6] %d/%d élèves mis à jour", updated, len(result.labels))

            # Garde-fou qualité : logge le verdict ; MAJ la baseline seulement si OK (recalcul appliqué)
            verdict = result.extra.get("quality", {})
            if verdict.get("niveau") and verdict["niveau"] != "OK":
                logger.warning("[MS6] Qualité clustering %s : %s",
                               verdict["niveau"], "; ".join(verdict.get("raisons", [])))
            maybe_maj_baseline(result.metrics, result.extra, verdict)

        except Exception as exc:
            logger.error("[MS6] Erreur clustering : %s", exc, exc_info=True)


_TRIGGERS = (
    "eleve.created", "eleve.gps.updated", "eleve.deleted",  # démographie élèves
    "bus.created", "bus.deleted",                            # flotte (capacité totale → k)
)


async def _on_message(message: aio_pika.IncomingMessage):
    async with message.process():
        logger.info("[MS6] Message reçu — routing_key=%s", message.routing_key)
        if message.routing_key in _TRIGGERS:
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
        for key in _TRIGGERS:
            await queue.bind(exchange, routing_key=key)
        await queue.consume(_on_message)

        logger.info("[MS6] Consumer RabbitMQ démarré")
    except Exception as exc:
        logger.error("[MS6] RabbitMQ inaccessible : %s — mode dégradé", exc)