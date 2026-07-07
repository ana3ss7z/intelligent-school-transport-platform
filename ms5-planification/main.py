"""
MS5 — PlanificationService / VRP (FastAPI, port 8085)
Optimisation des tournées : pour chaque groupe MS6, ordre de ramassage optimal (TSP OR-Tools, distances OSRM).
Sécurité : JWT (ADMIN/CHAUFFEUR). CORS géré uniquement par la Gateway.
"""
from __future__ import annotations
import logging
from collections import defaultdict

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from ms2_client import get_all_eleves, get_eleves_groupe
from planner import planifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger(__name__)

security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("role", "") not in ("ADMIN", "CHAUFFEUR"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès réservé ADMIN/CHAUFFEUR")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalide")


app = FastAPI(title="MS5 — PlanificationService (VRP)", version="1.0.0")


@app.get("/api/planification/health")
async def health():
    return {"status": "UP", "service": "ms5-planification", "port": settings.port,
            "solver": "OR-Tools TSP (dépôt=école, distances OSRM)"}


@app.post("/api/planification/tournee", dependencies=[Depends(verify_token)])
async def tournee(groupeId: int, sens: str = "matin"):
    """Tournée optimale d'un groupe (bus)."""
    try:
        eleves = await get_eleves_groupe(groupeId)
    except Exception as e:
        raise HTTPException(502, f"MS2 inaccessible : {e}")
    if not eleves:
        raise HTTPException(404, f"Aucun élève pour le groupe {groupeId}")
    res = await planifier(eleves, sens=sens)
    return {"groupeId": groupeId, **res}


@app.post("/api/planification/tournees", dependencies=[Depends(verify_token)])
async def tournees(sens: str = "matin"):
    """Tournées de tous les groupes (lit l'affectation MS6 courante via MS2)."""
    try:
        eleves = await get_all_eleves()
    except Exception as e:
        raise HTTPException(502, f"MS2 inaccessible : {e}")

    groupes: dict[int, list] = defaultdict(list)
    for e in eleves:
        g = e.get("groupeId")
        if g is not None:
            groupes[g].append(e)
    if not groupes:
        raise HTTPException(404, "Aucun groupe (lancer le clustering MS6 avec appliquer=true)")

    tournees_out, dist_tot, duree_tot = [], 0.0, 0.0
    for g in sorted(groupes):
        r = await planifier(groupes[g], sens=sens)
        r["groupeId"] = g
        tournees_out.append(r)
        dist_tot += r["distance_m"]; duree_tot += r["duree_min"]

    gains = [t["gain_vs_baseline_%"] for t in tournees_out if t["n_arrets"] > 1]
    return {
        "sens": sens,
        "n_bus": len(tournees_out),
        "distance_totale_km": round(dist_tot / 1000.0, 2),
        "duree_totale_min": round(duree_tot, 1),
        "gain_moyen_%": round(sum(gains) / len(gains), 1) if gains else 0.0,
        "tournees": tournees_out,
    }
