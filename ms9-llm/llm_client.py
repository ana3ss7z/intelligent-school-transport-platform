"""
Client LLM agnostique — API OpenAI-compatible (`POST {base}/chat/completions`).
Fonctionne avec Groq, Gemini (endpoint compat), Cerebras, OpenRouter, Mistral…
Essaie le provider primaire puis bascule sur le fallback en cas d'erreur/429/timeout.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3          # tentatives par provider (sur 429/5xx/timeout)
_BACKOFF_BASE = 0.8       # secondes (exponentiel : 0.8, 1.6, 3.2…)


def _logger_usage(provider: dict, usage: dict | None) -> None:
    """
    Journalise la consommation de jetons de l'appel.

    Le quota Groq qui contraint réellement le service est le **TPM** (8 000 jetons/minute sur le
    palier gratuit), pas la fenêtre de contexte (131 072). Or le contexte est réenvoyé à CHAQUE
    itération de la boucle d'outils : sans cette trace, on grossit le prompt à l'aveugle.
    `prompt_tokens` est la valeur à surveiller quand on ajoute du contexte au prompt système.
    """
    if not usage:
        return
    logger.info(
        "[MS9] jetons %s/%s — entrée %s · sortie %s · total %s",
        provider.get("name"), provider.get("model"),
        usage.get("prompt_tokens"), usage.get("completion_tokens"), usage.get("total_tokens"),
    )


class LLMNotConfigured(Exception):
    """Aucune clé LLM configurée (mode dégradé)."""


class LLMUnavailable(Exception):
    """Tous les providers configurés ont échoué."""


async def chat_completion(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Appelle le 1er provider disponible, bascule sur le suivant en cas d'échec.

    Retourne le `message` d'assistant brut (dict OpenAI : `content` et/ou `tool_calls`).
    """
    providers = settings.providers_order()
    if not providers:
        raise LLMNotConfigured()

    last_err: Exception | None = None
    for p in providers:
        payload: dict = {
            "model": p["model"],
            "messages": messages,
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
                    r = await client.post(
                        f"{p['base_url']}/chat/completions",
                        headers={"Authorization": f"Bearer {p['api_key']}"},
                        json=payload,
                    )
                if r.status_code == 200:
                    body = r.json()
                    _logger_usage(p, body.get("usage"))
                    return body["choices"][0]["message"]
                # 429 (rate limit) ou 5xx → réessayer le MÊME provider avec backoff
                if r.status_code == 429 or r.status_code >= 500:
                    last_err = LLMUnavailable(f"{p['name']} HTTP {r.status_code}")
                    if attempt < _MAX_RETRIES - 1:
                        await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))
                        continue
                    break  # épuisé → provider suivant
                # 4xx autre (clé invalide, requête malformée) → inutile de réessayer
                logger.warning("[MS9] Provider %s → HTTP %s : %s", p["name"], r.status_code, r.text[:200])
                last_err = LLMUnavailable(f"{p['name']} HTTP {r.status_code}")
                break
            except Exception as exc:  # timeout, réseau…
                last_err = exc
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))
                    continue
        logger.warning("[MS9] Provider %s épuisé : %s", p["name"], last_err)

    raise LLMUnavailable(str(last_err) if last_err else "aucun provider")
