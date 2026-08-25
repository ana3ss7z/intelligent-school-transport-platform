"""
MS9 — Assistant LLM (FastAPI, port 8089). Phase A : chatbot parent (tool-calling).
Sécurité : JWT (rôle PARENT). CORS géré uniquement par la Gateway.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import admin_agent
import agent
import db
from config import settings
from llm_client import LLMNotConfigured, LLMUnavailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Paramètres métier (MS13) : modèles de la cascade et clés API.
    # Chargés en premier — le reste de la configuration LLM en dépend.
    import params
    await params.demarrer()

    # Pool Postgres read-only pour le NL2SQL admin (mode dégradé si indisponible)
    await db.init_pool()
    yield
    await db.close_pool()


app = FastAPI(title="MS9 — Assistant LLM", version="1.0.0", lifespan=lifespan)
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


def auth_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Valide le JWT et exige le rôle ADMIN (NL2SQL, Phase B)."""
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalide")
    if payload.get("role", "") != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Assistant analytique réservé aux ADMIN")
    return payload


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None


class AdminQueryRequest(BaseModel):
    question: str
    history: list[dict] | None = None


@app.get("/api/llm/health")
async def health():
    providers = [p["name"] for p in settings.providers_order()]
    return {"status": "UP", "service": "ms9-llm", "port": settings.port,
            "providers": providers, "configured": bool(providers), "nl2sql": db.available()}


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


@app.get("/api/llm/admin/models-check")
async def models_check(user: dict = Depends(auth_admin)):
    """
    Interroge chaque fournisseur et dit lesquels des modèles configurés répondent encore.

    Pourquoi cet endpoint existe
    ----------------------------
    Les modèles LLM sont retirés du service sans préavis utile, et la cascade de MS9 masque
    la panne : tant qu'un étage répond, personne ne voit que les autres sont morts. C'est
    arrivé deux fois. Le 16/08, Groq a retiré toute la famille Llama — l'avis ne citait que
    le 70b, mais le 8b avait disparu aussi, donc les DEUX étages Groq échouaient en silence.
    Le 23/08, un test a révélé que `gemini-2.0-flash`, troisième et dernier étage, répondait
    404 sur la totalité des appels : le repli n'existait plus depuis des semaines.

    Cet appel transforme cette panne silencieuse en constat immédiat, depuis la page de
    configuration. À jouer avant chaque démonstration.

    Leçon associée : viser un ALIAS (`gemini-flash-latest`) plutôt qu'une version figée
    (`gemini-2.0-flash`) — un alias survit par construction aux changements de génération.
    """
    import httpx

    def _normaliser(identifiant: str) -> str:
        """
        Ramène un identifiant de modèle à une forme comparable entre fournisseurs.

        Les deux catalogues ne nomment pas leurs modèles de la même façon : Groq renvoie
        `openai/gpt-oss-120b`, Gemini renvoie `models/gemini-flash-latest` alors que l'appel
        se fait avec `gemini-flash-latest`. Sans ce retrait de préfixe, la comparaison exacte
        déclarait **tous** les modèles Gemini absents — une fausse alerte, c'est-à-dire pire
        qu'aucune vérification : elle aurait envoyé l'administrateur corriger une panne
        inexistante, et discrédité l'alerte le jour où elle est vraie.
        """
        return identifiant.removeprefix("models/")

    async def _interroger(nom: str, base_url: str, api_key: str, modeles: list[str]) -> dict:
        if not api_key:
            return {"fournisseur": nom, "statut": "sans_cle",
                    "detail": "aucune clé enregistrée", "modeles": []}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{base_url}/models",
                                     headers={"Authorization": f"Bearer {api_key}"})
                r.raise_for_status()
                data = r.json().get("data", [])
                servis = {_normaliser(m["id"]) for m in data
                          if isinstance(m, dict) and isinstance(m.get("id"), str)}
        except Exception as exc:
            return {"fournisseur": nom, "statut": "injoignable",
                    "detail": str(exc)[:200], "modeles": []}
        return {
            "fournisseur": nom, "statut": "ok", "n_servis": len(servis),
            "modeles": [{"modele": m, "servi": _normaliser(m) in servis} for m in modeles if m],
        }

    resultats = await asyncio.gather(
        _interroger("groq", settings.groq_base_url, settings.groq_api_key,
                    [settings.groq_model, settings.groq_fallback_model]),
        _interroger("gemini", settings.gemini_base_url, settings.gemini_api_key,
                    [settings.gemini_model]),
    )

    manquants = [m["modele"] for r in resultats for m in r["modeles"] if not m["servi"]]
    return {
        "resultats": list(resultats),
        "cascade": [f"{p['name']}:{p['model']}" for p in settings.providers_order()],
        "modeles_absents": manquants,
        "verdict": "OK" if not manquants else "MODELES_ABSENTS",
    }


@app.post("/api/llm/admin/query")
async def admin_query(req: AdminQueryRequest, user: dict = Depends(auth_admin)):
    """NL2SQL admin : question langage naturel → SQL read-only → réponse + SQL + tableau."""
    if not req.question.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Question vide")
    try:
        return await admin_agent.run(req.question, req.history)
    except LLMNotConfigured:
        return {"reply": DEGRADE_MSG, "sql": None, "colonnes": [], "lignes": [], "degraded": True}
    except LLMUnavailable as exc:
        logger.error("[MS9] LLM indisponible (admin) : %s", exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Assistant momentanément indisponible.")
    except Exception as exc:
        logger.exception("[MS9] Erreur admin/query : %s", exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Erreur interne de l'assistant.")
