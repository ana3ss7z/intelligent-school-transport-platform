"""
Agent conversationnel parent — boucle function-calling « maison » (sans LangChain).
Pré-fetch des enfants (1×), tool calls en parallèle, historique propre (user/assistant seulement).
"""
from __future__ import annotations

import asyncio
import json
import logging

from config import settings
from llm_client import chat_completion
from school_facts import FAITS_ECOLE
from tools import ToolContext, TOOLS_SCHEMA, execute_tool, parse_args, prefetch_children, _resume_enfants

logger = logging.getLogger(__name__)


def _system_prompt(nom: str, enfants: list[dict]) -> str:
    resume = _resume_enfants(enfants)
    # Socle « école » : ancre les questions générales (horaires, procédures, règlement) sur des faits
    # au lieu de la mémoire du modèle. Désactivable pour mesurer l'écart avec/sans (cf. config).
    socle = f"\n\n{FAITS_ECOLE}" if settings.school_facts_enabled else ""
    return (
        f"Tu es l'assistant de transport scolaire du parent {nom}. "
        "Réponds toujours dans la langue du dernier message (français, arabe standard ou darija). "
        "Sois bref, clair et rassurant.\n"
        "RÈGLES IMPORTANTES :\n"
        "1. Réponds EXACTEMENT à la question posée ; ne substitue jamais une autre information.\n"
        "2. Les outils servent UNIQUEMENT à obtenir des infos sur le BUS/l'enfant (position, ETA, présence, "
        "incidents, trajet). N'appelle AUCUN outil pour une question qui ne porte pas sur le bus.\n"
        "3. Si la question porte sur l'ÉCOLE, le transport en général ou une procédure (horaires, absence, "
        "règlement, inscription, contact), n'appelle AUCUN outil : réponds uniquement à partir des "
        "CONNAISSANCES ÉCOLE données plus bas.\n"
        "4. N'invente jamais une position, une heure, un statut, un horaire, un délai, un tarif ni une règle. "
        "Pour le bus, appuie-toi sur les outils ; pour l'école et les procédures, sur les CONNAISSANCES ÉCOLE. "
        "Si l'information ne figure ni dans les outils ni dans ces connaissances, dis simplement que tu ne l'as "
        "pas et invite le parent à contacter l'administration de l'école. Ne comble jamais un manque par une "
        "réponse plausible.\n"
        "5. Tu ne peux renseigner que sur les enfants de ce parent ; refuse poliment toute demande sur d'autres bus/élèves.\n"
        "6. Pour une position de bus, utilise le champ « lieu » (rue/quartier) renvoyé par l'outil "
        "(ex. « près de {lieu} ») ; ne cite JAMAIS de coordonnées brutes (latitude/longitude) au parent. "
        "Ajoute l'ETA si pertinent (« à ~N min de l'école »).\n"
        f"Contexte enfants (source de vérité pour les busId) : {json.dumps(resume, ensure_ascii=False)}"
        f"{socle}"
    )


def _assistant_spec(assistant: dict) -> dict:
    """Message d'assistant réduit aux champs de la spec OpenAI (role/content/tool_calls).

    Les modèles gpt-oss renvoient en plus un champ `reasoning`, et parfois AUCUN `content`
    quand ils appellent un outil. On normalise pour que l'historique reste rejouable par
    n'importe quel provider de la cascade.
    """
    out: dict = {"role": assistant.get("role", "assistant"),
                 "content": assistant.get("content") or ""}
    if assistant.get("tool_calls"):
        out["tool_calls"] = assistant["tool_calls"]
    return out


def _clean_history(history: list[dict] | None) -> list[dict]:
    """Ne garde que les tours user/assistant en texte (jamais de tool/tool_calls) — évite le 400 OpenAI."""
    if not history:
        return []
    out = []
    for m in history:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content})
    # borne aux N derniers tours (2 messages / tour)
    return out[-settings.history_max_turns * 2:]


async def run(bearer: str, parent_id: int, parent_nom: str, message: str,
              history: list[dict] | None = None) -> dict:
    ctx = ToolContext(bearer=bearer, parent_id=parent_id)
    try:
        await prefetch_children(ctx)
    except Exception as exc:
        logger.warning("[MS9] Pré-fetch enfants échoué : %s", exc)

    messages = [{"role": "system", "content": _system_prompt(parent_nom, ctx.enfants)}]
    messages += _clean_history(history)
    messages.append({"role": "user", "content": message})

    used_tools: list[str] = []
    for _ in range(settings.max_tool_iters):
        assistant = await chat_completion(messages, TOOLS_SCHEMA)
        tool_calls = assistant.get("tool_calls") or []

        if not tool_calls:
            return {"reply": assistant.get("content") or "", "used_tools": used_tools}

        # Garder le message assistant (avec tool_calls) AVANT les messages tool (spec OpenAI),
        # mais réduit aux champs de la spec : gpt-oss ajoute un champ `reasoning` propriétaire.
        # Le renvoyer tel quel marche chez Groq, pas forcément chez le provider suivant — or la
        # cascade peut basculer sur Gemini EN COURS de conversation, avec cet historique.
        # Bonus : on cesse de repayer les jetons de raisonnement à chaque tour.
        messages.append(_assistant_spec(assistant))

        async def _one(call: dict) -> dict:
            fn = call.get("function", {})
            name = fn.get("name", "")
            used_tools.append(name)
            result = await execute_tool(ctx, name, parse_args(fn.get("arguments")))
            return {"role": "tool", "tool_call_id": call.get("id"),
                    "content": json.dumps(result, ensure_ascii=False)}

        # Exécution parallèle des outils du tour
        tool_msgs = await asyncio.gather(*[_one(c) for c in tool_calls])
        messages.extend(tool_msgs)

    # Dernier appel sans outils pour forcer une réponse texte
    final = await chat_completion(messages, None)
    return {"reply": final.get("content") or "Je n'ai pas pu formuler de réponse.", "used_tools": used_tools}
