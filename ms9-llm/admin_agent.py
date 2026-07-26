"""
Agent NL2SQL admin (Phase B) — question langage naturel → SQL PostgreSQL read-only → réponse.
Un seul outil `execute_sql` (validé + exécuté en lecture seule), avec auto-correction sur erreur SQL.
Réutilise la cascade providers de llm_client.
"""
from __future__ import annotations

import json
import logging

import db
from config import settings
from llm_client import chat_completion
from schema_prompt import SCHEMA
from sql_guard import SqlRejected, valider_et_normaliser

logger = logging.getLogger(__name__)

_LLM_ROWS = 40  # nb de lignes max renvoyées AU LLM (le front en reçoit jusqu'à sql_max_rows)

_TOOL = [{
    "type": "function", "function": {
        "name": "execute_sql",
        "description": "Exécute UNE requête SELECT PostgreSQL en lecture seule et renvoie les lignes. "
                       "Utilise-la pour toute donnée chiffrée. Corrige et relance si une erreur est renvoyée.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Requête SELECT (PostgreSQL, colonnes explicites, avec LIMIT)"}
        }, "required": ["query"]},
    },
}]


def _system_prompt() -> str:
    return (
        "Tu es un analyste de données pour l'administration d'un système de transport scolaire. "
        "Traduis la question de l'admin en UNE requête SQL PostgreSQL (lecture seule), exécute-la via l'outil "
        "`execute_sql`, puis réponds en langage naturel (langue de la question : français ou arabe), de façon "
        "concise et chiffrée. N'invente JAMAIS de chiffres : appuie-toi uniquement sur les résultats de l'outil. "
        "Si l'outil renvoie une erreur, corrige la requête et relance. Si la question est ambiguë, demande une "
        "précision. Si elle ne concerne pas les données, réponds poliment sans exécuter de requête.\n\n" + SCHEMA
    )


async def run(question: str, history: list[dict] | None = None) -> dict:
    if not db.available():
        return {"reply": "L'assistant analytique n'est pas configuré (base read-only indisponible). "
                         "Vérifiez le rôle ms9_readonly et DB_RO_PASSWORD.", "sql": None,
                "colonnes": [], "lignes": [], "degraded": True}

    messages = [{"role": "system", "content": _system_prompt()}]
    for m in (history or [])[-6:]:
        if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": question})

    last_sql: str | None = None
    last_full: dict | None = None   # résultat complet (pour le front)

    for _ in range(settings.max_tool_iters):
        assistant = await chat_completion(messages, _TOOL)
        calls = assistant.get("tool_calls") or []
        if not calls:
            return {"reply": assistant.get("content") or "", "sql": last_sql,
                    "colonnes": (last_full or {}).get("colonnes", []),
                    "lignes": (last_full or {}).get("lignes", []),
                    "tronque": (last_full or {}).get("tronque", False)}
        messages.append(assistant)
        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            tool_out: dict
            # Dispatch explicite : tout outil non déclaré est refusé (jamais exécuté)
            if name != "execute_sql":
                messages.append({"role": "tool", "tool_call_id": call.get("id"),
                                 "content": json.dumps({"erreur": f"Outil inconnu : {name}"}, ensure_ascii=False)})
                continue
            args = fn.get("arguments")
            try:
                raw = json.loads(args) if isinstance(args, str) else (args or {})
            except Exception:
                raw = {}
            query = raw.get("query", "")
            try:
                sql = valider_et_normaliser(query)
                last_sql = sql
                res = await db.run_readonly(sql)
                last_full = res
                # version allégée pour le LLM (tokens)
                tool_out = {"colonnes": res["colonnes"], "lignes": res["lignes"][:_LLM_ROWS],
                            "n": res["n"], "tronque": res["tronque"] or res["n"] > _LLM_ROWS}
            except SqlRejected as e:
                tool_out = {"erreur": f"Requête refusée (sécurité) : {e}"}
            except Exception as e:
                tool_out = {"erreur": f"Erreur SQL : {str(e)[:300]}"}
            messages.append({"role": "tool", "tool_call_id": call.get("id"),
                             "content": json.dumps(tool_out, ensure_ascii=False, default=str)})

    # boucle épuisée → réponse texte finale sans outil
    final = await chat_completion(messages, None)
    return {"reply": final.get("content") or "Je n'ai pas pu formuler de réponse.", "sql": last_sql,
            "colonnes": (last_full or {}).get("colonnes", []), "lignes": (last_full or {}).get("lignes", []),
            "tronque": (last_full or {}).get("tronque", False)}
