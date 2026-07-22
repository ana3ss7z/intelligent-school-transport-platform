"""
Client LLM agnostique — API OpenAI-compatible (`POST {base}/chat/completions`).
Fonctionne avec Groq, Gemini (endpoint compat), Cerebras, OpenRouter, Mistral…
Essaie le provider primaire puis bascule sur le fallback en cas d'erreur/429/timeout.
"""
from __future__ import annotations

import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


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
        try:
            async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
                r = await client.post(
                    f"{p['base_url']}/chat/completions",
                    headers={"Authorization": f"Bearer {p['api_key']}"},
                    json=payload,
                )
            if r.status_code != 200:
                logger.warning("[MS9] Provider %s → HTTP %s : %s", p["name"], r.status_code, r.text[:200])
                last_err = LLMUnavailable(f"{p['name']} HTTP {r.status_code}")
                continue
            data = r.json()
            return data["choices"][0]["message"]
        except Exception as exc:  # timeout, réseau, JSON…
            logger.warning("[MS9] Provider %s indisponible : %s", p["name"], exc)
            last_err = exc
            continue

    raise LLMUnavailable(str(last_err) if last_err else "aucun provider")
