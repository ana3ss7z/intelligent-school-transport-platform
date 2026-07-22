"""
MS9 — Assistant LLM (FastAPI, port 8089). Phase A : chatbot parent (tool-calling).
Sécurité : JWT (rôle PARENT). CORS géré uniquement par la Gateway.
"""
from __future__ import annotations

import logging

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import agent
from config import settings
from llm_client import LLMNotConfigured, LLMUnavailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="MS9 — Assistant LLM", version="1.0.0")
security = HTTPBearer()

DEGRADE_MSG = ("L'assistant n'est pas encore configuré (aucune clé LLM). "
               "Ajoutez GROQ_API_KEY ou GEMINI_API_KEY dans ms9-llm/.env.")


def auth_parent(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Valide le JWT (même secret que MS7) et exige le rôle PARENT (Phase A)."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalide")
    if payload.get("role", "") != "PARENT":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Assistant réservé aux parents (Phase A)")
    payload["_bearer"] = token
    return payload


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None


@app.get("/api/llm/health")
async def health():
    providers = [p["name"] for p in settings.providers_order()]
    return {"status": "UP", "service": "ms9-llm", "port": settings.port,
            "providers": providers, "configured": bool(providers)}


@app.get("/api/llm/model-info")
async def model_info():
    return {"phase": "A — chatbot parent (tool-calling)",
            "primary": settings.primary_provider, "fallback": settings.fallback_provider,
            "providers_configures": [p["name"] for p in settings.providers_order()],
            "outils": ["get_mes_enfants", "get_position_bus", "get_eta_ecole", "get_trajet_actif", "get_incidents_bus"]}


@app.post("/api/llm/chat")
async def chat(req: ChatRequest, user: dict = Depends(auth_parent)):
    if not req.message.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Message vide")
    parent_id = user.get("userId")
    nom = user.get("nom") or "parent"
    try:
        result = await agent.run(user["_bearer"], parent_id, nom, req.message, req.history)
        return result
    except LLMNotConfigured:
        return {"reply": DEGRADE_MSG, "used_tools": [], "degraded": True}
    except LLMUnavailable as exc:
        logger.error("[MS9] LLM indisponible : %s", exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Assistant momentanément indisponible.")
    except Exception as exc:
        logger.exception("[MS9] Erreur chat : %s", exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Erreur interne de l'assistant.")
