"""
Consumer RabbitMQ MS6 — recalcule le clustering après chaque événement élève.
Utilise bulk update (1 requête HTTP) au lieu de N PATCH simultanés.
"""
import asyncio
import json
import logging
import aio_pika
from config import settings
from binding import appliquer_bus
from clustering import production_clustering, verrou_calcul
from ms2_client import assigner_groupes_bulk, get_all_eleves
from quality import maybe_maj_baseline
import etat

logger = logging.getLogger(__name__)
# Le verrou vit desormais dans `clustering.py` : il doit etre partage avec main.py.


async def publier(routing_key: str, payload: dict) -> None:
    """Publie un événement sur l'exchange (ex. alerte qualité → MS4). content_type text/plain (compat MS4)."""
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(settings.exchange_name, aio_pika.ExchangeType.TOPIC, durable=True)
            await exchange.publish(
                aio_pika.Message(body=json.dumps(payload).encode(), content_type="text/plain"),
                routing_key=routing_key)
    except Exception as exc:
        logger.warning("[MS6] Publication %s échouée : %s", routing_key, exc)


async def signaler_qualite(result) -> None:
    """Publie clustering.quality.low si le verdict qualité n'est pas OK (canal admin D1)."""
    q = result.extra.get("quality", {})
    if q.get("niveau") and q["niveau"] != "OK":
        await publier("clustering.quality.low", {
            "niveau": q["niveau"], "raisons": q.get("raisons", []),
            "silhouette": result.silhouette, "k": result.k,
            "n_disperses": result.extra.get("n_disperses", 0),
        })


async def _recalculer_et_ecrire():
    async with verrou_calcul:
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

            # Liaison groupe↔bus : propage busId (rend notifs/ETA fonctionnels)
            rapport = await appliquer_bus(result.labels)
            logger.info("[MS6] Liaison bus : %d élèves liés (%d/%d groupes)",
                        rapport.get("n_lies", 0), rapport.get("k", 0) - rapport.get("manque_bus", 0), rapport.get("k", 0))

            # Garde-fou qualité : logge le verdict ; MAJ la baseline seulement si OK (recalcul appliqué)
            verdict = result.extra.get("quality", {})
            if verdict.get("niveau") and verdict["niveau"] != "OK":
                logger.warning("[MS6] Qualité clustering %s : %s",
                               verdict["niveau"], "; ".join(verdict.get("raisons", [])))
                await signaler_qualite(result)          # canal admin (D1)
            maybe_maj_baseline(result.metrics, result.extra, verdict)
            etat.enregistrer(result.k, len(result.labels),
                             result.extra["capacity"], result.extra["rayon_max_m"])

        except Exception as exc:
            logger.error("[MS6] Erreur clustering : %s", exc, exc_info=True)


_TRIGGERS = (
    "eleve.created", "eleve.gps.updated", "eleve.deleted",  # démographie élèves
    "bus.created", "bus.deleted",                            # flotte (capacité totale → k)
)


async def _on_message(message: aio_pika.IncomingMessage):
    async with message.process():
        logger.info("[MS6] Message reçu — routing_key=%s", message.routing_key)
        if message.routing_key not in _TRIGGERS:
            return
        # Interrupteur d'exploitation (MS13, `ms6.recalcul_auto`). Le message est bien consommé
        # et acquitté : on ne veut pas qu'il s'accumule dans la file pour se déverser d'un coup
        # à la réactivation — ce serait précisément la rafale de recalculs qu'on cherche à éviter.
        # Le recalcul reste disponible à la demande via POST /api/clustering/production.
        if not settings.recalcul_auto:
            logger.info("[MS6] Recalcul automatique désactivé (ms6.recalcul_auto) — %s ignoré",
                        message.routing_key)
            return
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