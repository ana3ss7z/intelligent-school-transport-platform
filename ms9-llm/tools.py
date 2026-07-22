"""
Outils du chatbot parent (Phase A). Chaque outil appelle un microservice interne
AVEC le JWT du parent, et est strictement limité aux enfants du parent (garde de portée).
On ne fait JAMAIS confiance à un busId proposé par le LLM : il doit appartenir à `allowed_bus_ids`.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import httpx

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    bearer: str
    parent_id: int
    allowed_bus_ids: set[int] = field(default_factory=set)
    enfants: list[dict] = field(default_factory=list)


def _headers(ctx: ToolContext) -> dict:
    return {"Authorization": f"Bearer {ctx.bearer}"}


async def prefetch_children(ctx: ToolContext) -> list[dict]:
    """Récupère les enfants du parent (MS2) — appelé UNE fois par requête /chat."""
    async with httpx.AsyncClient(timeout=settings.http_timeout) as c:
        r = await c.get(f"{settings.ms2_url}/api/eleves/parent/{ctx.parent_id}", headers=_headers(ctx))
        r.raise_for_status()
        enfants = r.json()
    ctx.enfants = enfants
    ctx.allowed_bus_ids = {e["busId"] for e in enfants if e.get("busId") is not None}
    return enfants


def _resume_enfants(enfants: list[dict]) -> list[dict]:
    return [{
        "id": e.get("id"), "nom": f"{e.get('prenom','')} {e.get('nom','')}".strip(),
        "busId": e.get("busId"), "groupeId": e.get("groupeId"),
        "present": e.get("statutPresence"),
    } for e in enfants]


# ── Schémas OpenAI (function calling) ─────────────────────────────────
TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "get_mes_enfants",
        "description": "Liste les enfants du parent connecté (nom, bus assigné, groupe, statut de présence à bord).",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_position_bus",
        "description": "Dernière position GPS connue d'un bus (latitude, longitude, vitesse).",
        "parameters": {"type": "object", "properties": {
            "busId": {"type": "integer", "description": "id du bus (doit être celui d'un enfant du parent)"}
        }, "required": ["busId"]},
    }},
    {"type": "function", "function": {
        "name": "get_eta_ecole",
        "description": "Temps estimé (minutes) pour que le bus atteigne l'école, à partir de sa position actuelle.",
        "parameters": {"type": "object", "properties": {
            "busId": {"type": "integer"}
        }, "required": ["busId"]},
    }},
    {"type": "function", "function": {
        "name": "get_trajet_actif",
        "description": "Indique si un trajet est en cours pour ce bus et son sens (matin/soir).",
        "parameters": {"type": "object", "properties": {
            "busId": {"type": "integer"}
        }, "required": ["busId"]},
    }},
    {"type": "function", "function": {
        "name": "get_incidents_bus",
        "description": "Incidents récents (panne, retard, accident…) déclarés sur ce bus.",
        "parameters": {"type": "object", "properties": {
            "busId": {"type": "integer"}
        }, "required": ["busId"]},
    }},
]


def _check_scope(ctx: ToolContext, bus_id) -> int | None:
    try:
        bid = int(bus_id)
    except (TypeError, ValueError):
        return None
    return bid if bid in ctx.allowed_bus_ids else None


async def execute_tool(ctx: ToolContext, name: str, args: dict) -> dict:
    """Exécute un outil. Retourne un dict JSON-sérialisable (résultat ou erreur)."""
    try:
        if name == "get_mes_enfants":
            return {"enfants": _resume_enfants(ctx.enfants)}

        if name in ("get_position_bus", "get_eta_ecole", "get_trajet_actif", "get_incidents_bus"):
            bid = _check_scope(ctx, args.get("busId"))
            if bid is None:
                return {"refus": "Information non disponible : ce bus ne concerne pas vos enfants."}

            async with httpx.AsyncClient(timeout=settings.http_timeout) as c:
                if name == "get_position_bus":
                    r = await c.get(f"{settings.ms3_url}/api/gps/bus/{bid}/derniere", headers=_headers(ctx))
                    if r.status_code == 404:
                        return {"position": None, "info": "Aucune position GPS récente pour ce bus."}
                    r.raise_for_status()
                    p = r.json()
                    return {"busId": bid, "latitude": p.get("latitude"), "longitude": p.get("longitude"),
                            "vitesse": p.get("vitesse"), "horodatage": p.get("horodatage")}

                if name == "get_trajet_actif":
                    r = await c.get(f"{settings.ms1_url}/api/trajets/bus/{bid}/actif", headers=_headers(ctx))
                    if r.status_code == 204:
                        return {"busId": bid, "trajet_en_cours": False}
                    r.raise_for_status()
                    t = r.json()
                    return {"busId": bid, "trajet_en_cours": True, "sens": t.get("sens"),
                            "heureDebut": t.get("heureDebut")}

                if name == "get_incidents_bus":
                    r = await c.get(f"{settings.ms10_url}/api/incidents/bus/{bid}", headers=_headers(ctx))
                    r.raise_for_status()
                    inc = r.json()
                    return {"busId": bid, "incidents": [
                        {"type": i.get("type"), "statut": i.get("statut"),
                         "description": i.get("description"), "date": i.get("dateSignalement")}
                        for i in inc[:5]
                    ]}

                if name == "get_eta_ecole":
                    pr = await c.get(f"{settings.ms3_url}/api/gps/bus/{bid}/derniere", headers=_headers(ctx))
                    if pr.status_code == 404:
                        return {"busId": bid, "eta_minutes": None, "info": "Position du bus inconnue."}
                    pr.raise_for_status()
                    pos = pr.json()
                    er = await c.post(f"{settings.ms12_url}/api/eta/predict", headers=_headers(ctx), json={
                        "auto_context": True,
                        "bus_lat": pos.get("latitude"), "bus_lng": pos.get("longitude"),
                        "dest_lat": settings.ecole_lat, "dest_lng": settings.ecole_lng, "moment": "matin",
                    })
                    er.raise_for_status()
                    eta = er.json()
                    return {"busId": bid, "eta_minutes": round(eta.get("eta_minutes", 0), 1)}

        return {"erreur": f"Outil inconnu : {name}"}
    except Exception as exc:
        logger.warning("[MS9] Outil %s a échoué : %s", name, exc)
        return {"erreur": "Service temporairement indisponible."}


def parse_args(raw: str | dict) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}
