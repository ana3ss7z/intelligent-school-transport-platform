"""
Synchronisation des paramètres depuis MS13 — module partagé (copie par service).
================================================================================

Le service lit sa configuration métier dans MS13 au démarrage, puis se remet à jour
**à chaud** quand l'administrateur enregistre un changement. Aucun redémarrage.

Pourquoi une simple mutation de `settings` suffit
-------------------------------------------------
Tous les services Python de ce projet lisent `settings.x` **au moment de l'appel**, jamais
à l'import (vérifié : `live_monitor.py` relit `settings.seuil_vitesse_kmh` à chaque ping,
`main.py` relit `settings.bus_capacity` à chaque requête). Réaffecter l'attribut du singleton
pydantic est donc immédiatement visible par le code métier, sans rechargement de module.

Trois chemins de mise à jour, du plus rapide au plus robuste
------------------------------------------------------------
1. **Événement** `parametres.updated` (RabbitMQ) — latence de l'ordre de la milliseconde ;
2. **Rafraîchissement périodique** — filet si le courtier est absent ou si un message est perdu ;
3. **Démarrage** — un service qui redémarre repart de la source de vérité, pas de son `.env`.

Le message ne transporte que les clés modifiées ; les valeurs sont toujours relues depuis
MS13. Un message perdu, dupliqué ou réordonné ne peut donc pas laisser deux services avec
des visions différentes — et aucune clé API ne transite par le bus de messages.

Mode dégradé
------------
Si MS13 est injoignable, le service démarre quand même avec les valeurs de son `.env`.
La configuration est un confort d'exploitation, pas une dépendance dure : un incident sur
MS13 ne doit pas empêcher de calculer une tournée.

⚠️ Ce fichier est **dupliqué à l'identique** dans les cinq services Python (même choix
assumé que pour `route_eta.dart`, dupliqué entre les deux applications Flutter). Seul le
dictionnaire `MAPPING`, en tête, diffère : il déclare les clés que CE service consomme.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

# ── Partie propre à ce service ────────────────────────────────────────────────
# clé du catalogue MS13 → attribut de `settings`.
# Une clé absente d'ici est ignorée : chaque service ne s'applique que ce qui le concerne.
MAPPING: dict[str, str] = {
    "ecole.lat":             "ecole_lat",
    "ecole.lng":             "ecole_lng",
    "ms5.vrp_time_limit_s":  "vrp_time_limit_s",
}

SERVICE = "MS5"

# ── Machinerie commune (identique dans les cinq services) ─────────────────────

_INTERVALLE_FILET_S = 120.0


def _convertir(brut: str, actuel):
    """
    Convertit la valeur texte de MS13 vers le type de l'attribut existant.

    Le type courant fait référence : il vient de l'annotation pydantic, donc de la
    déclaration du service. On ne redéclare pas les types côté MS13, ce qui éviterait
    difficilement qu'ils divergent un jour de ceux d'ici.
    """
    if isinstance(actuel, bool):
        # À faire avant le cas `int` : en Python, bool EST un int, et `bool("false")`
        # vaut True — toute chaîne non vide est vraie. Sans ce cas explicite, désactiver
        # une option depuis l'interface l'activerait.
        return brut.strip().lower() in ("true", "1", "yes", "on")
    if isinstance(actuel, int):
        return int(float(brut))
    if isinstance(actuel, float):
        return float(brut)
    return brut


async def charger(url: str | None = None) -> int:
    """
    Relit MS13 et applique les valeurs à `settings`.

    :return: nombre d'attributs réellement modifiés (0 si rien n'a bougé ou si MS13 est absent)
    """
    base = url or getattr(settings, "ms13_url", "http://localhost:8092")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base}/api/parametres/internal")
            r.raise_for_status()
            valeurs: dict[str, str] = r.json()
    except Exception as exc:
        logger.warning("[%s] MS13 injoignable (%s) — configuration locale (.env) conservée",
                       SERVICE, exc)
        return 0

    changes: list[str] = []
    for cle, champ in MAPPING.items():
        if cle not in valeurs:
            continue
        actuel = getattr(settings, champ, None)
        if actuel is None and not hasattr(settings, champ):
            logger.warning("[%s] %s → settings.%s : attribut inexistant, ignoré",
                           SERVICE, cle, champ)
            continue

        # Une valeur vide côté MS13 signifie « non renseignée », pas « effacer ».
        #
        # Ce cas s'est produit en réel : MS13 démarre avec ses clés API vides (elles ne sont
        # pas dans le catalogue, un secret n'a pas de défaut), et MS9 a consciencieusement
        # remplacé ses clés Groq et Gemini — pourtant valides, lues depuis son `.env` — par
        # des chaînes vides. L'assistant serait tombé en panne au premier message, sans autre
        # trace qu'un « mode dégradé » dans les journaux.
        #
        # Le `.env` reste donc l'amorçage : MS13 ne prend le dessus que lorsqu'il a
        # effectivement quelque chose à dire. Pour vider délibérément un réglage textuel, on
        # passe par le `.env` du service — la console d'administration ne sert pas à effacer.
        if valeurs[cle] == "" and isinstance(actuel, str) and actuel != "":
            continue
        try:
            nouvelle = _convertir(valeurs[cle], actuel)
        except (TypeError, ValueError) as exc:
            logger.warning("[%s] %s = %r inconvertible (%s) — valeur conservée",
                           SERVICE, cle, valeurs[cle], exc)
            continue
        if nouvelle != actuel:
            setattr(settings, champ, nouvelle)
            # Ne jamais journaliser la valeur d'une clé d'API.
            if "key" in champ or "password" in champ:
                changes.append(f"{champ}: (secret modifié)")
            else:
                changes.append(f"{champ}: {actuel!r} → {nouvelle!r}")

    if changes:
        logger.info("[%s] Paramètres appliqués — %s", SERVICE, " · ".join(changes))
    return len(changes)


async def _boucle_filet() -> None:
    """Relecture périodique : rattrape un courtier absent ou un message perdu."""
    while True:
        await asyncio.sleep(_INTERVALLE_FILET_S)
        try:
            await charger()
        except Exception as exc:
            logger.debug("[%s] Rafraîchissement périodique échoué : %s", SERVICE, exc)


async def _ecouter_evenements() -> None:
    """S'abonne à `parametres.updated`. Silencieux si RabbitMQ est absent."""
    try:
        import aio_pika
    except ImportError:
        logger.debug("[%s] aio_pika absent — seul le filet périodique est actif", SERVICE)
        return

    # Tous les services n'ont pas de courtier configuré (MS5 et MS9 n'en avaient aucun usage
    # avant MS13). Sans URL, on ne tente rien : le filet périodique suffit.
    url = getattr(settings, "rabbitmq_url", None)
    if not url:
        logger.debug("[%s] Aucun RabbitMQ configuré — seul le filet périodique est actif", SERVICE)
        return

    try:
        connection = await aio_pika.connect_robust(url)
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            getattr(settings, "exchange_name", "transport.exchange"),
            aio_pika.ExchangeType.TOPIC, durable=True)

        # File EXCLUSIVE et auto-supprimée, une par instance de service.
        # Une file durable partagée serait un contresens : RabbitMQ distribue alors les
        # messages en tourniquet entre les consommateurs, si bien qu'un seul service
        # recevrait chaque changement — les autres resteraient sur d'anciennes valeurs.
        # Ici, chacun doit recevoir chaque événement : il lui faut sa propre file.
        queue = await channel.declare_queue("", exclusive=True, auto_delete=True)
        await queue.bind(exchange, routing_key="parametres.updated")

        async def _on_message(message):
            async with message.process():
                cles = message.body.decode()
                if not any(c.strip() in MAPPING for c in cles.split(",")):
                    return          # changement qui ne nous concerne pas
                logger.info("[%s] Changement de paramètres signalé (%s)", SERVICE, cles)
                await charger()

        await queue.consume(_on_message)
        logger.info("[%s] Abonné à parametres.updated (mise à jour à chaud active)", SERVICE)
    except Exception as exc:
        logger.warning("[%s] Abonnement aux paramètres impossible (%s) — "
                       "repli sur le rafraîchissement périodique (%.0f s)",
                       SERVICE, exc, _INTERVALLE_FILET_S)


async def demarrer() -> None:
    """À appeler dans le `lifespan` du service, avant de servir la première requête."""
    await charger()
    asyncio.create_task(_ecouter_evenements())
    asyncio.create_task(_boucle_filet())
