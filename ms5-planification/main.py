"""
MS5 — PlanificationService / VRP (FastAPI, port 8085)
Optimisation des tournées : pour chaque groupe MS6, ordre de ramassage optimal (TSP OR-Tools, distances OSRM).
Sécurité : JWT (ADMIN/CHAUFFEUR). CORS géré uniquement par la Gateway.
"""
from __future__ import annotations
import asyncio
import logging
from collections import defaultdict

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from ms2_client import get_all_eleves, get_eleves_groupe, assigner_ordre_bulk
from planner import planifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger(__name__)

security = HTTPBearer()


def _decoder(credentials: HTTPAuthorizationCredentials) -> dict:
    try:
        return jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalide")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decoder(credentials)
    if payload.get("role", "") not in ("ADMIN", "CHAUFFEUR"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès réservé ADMIN/CHAUFFEUR")
    return payload


def verify_parent(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Accès parent — la **portée vient du jeton**, jamais de la requête.

    Les tournées complètes (`/tournee`, `/tournees`) restent interdites aux parents : elles
    contiennent le domicile de tous les élèves du bus. Le parent n'obtient que les étapes de
    SES enfants, via `parentId` extrait du JWT.
    """
    payload = _decoder(credentials)
    if payload.get("role", "") != "PARENT":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès réservé PARENT")
    if payload.get("userId") is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Jeton sans identifiant parent")
    return payload


app = FastAPI(title="MS5 — PlanificationService (VRP)", version="1.0.0")


@app.get("/api/planification/health")
async def health():
    return {"status": "UP", "service": "ms5-planification", "port": settings.port,
            "solver": "OR-Tools TSP (dépôt=école, distances OSRM)"}


@app.post("/api/planification/tournee", dependencies=[Depends(verify_token)])
async def tournee(groupeId: int, sens: str = "matin", persister: bool = True):
    """Tournée optimale d'un groupe (bus). `persister` → écrit l'ordre de passage dans MS2."""
    try:
        eleves = await get_eleves_groupe(groupeId)
    except Exception as e:
        raise HTTPException(502, f"MS2 inaccessible : {e}")
    if not eleves:
        raise HTTPException(404, f"Aucun élève pour le groupe {groupeId}")
    res = await planifier(eleves, sens=sens)
    if persister and res.get("ordre"):
        res["persiste"] = await assigner_ordre_bulk({int(eid): i + 1 for i, eid in enumerate(res["ordre"])})
    return {"groupeId": groupeId, **res}


@app.post("/api/planification/mes-enfants")
async def eta_mes_enfants(sens: str = "matin", payload: dict = Depends(verify_parent)):
    """
    Étapes de la tournée **pour les seuls enfants du parent connecté**.

    Renvoie, par enfant, son rang de passage et le **cumul depuis l'école** (distance + durée
    OSRM libre). L'appelant passe ensuite ce cumul à MS12 (`distance_routiere_m` / `duree_base_s`)
    pour obtenir l'heure d'arrivée estimée dans les conditions du jour.

    Aucun autre élève n'est exposé : ni nom, ni domicile, ni rang.
    """
    parent_id = int(payload["userId"])
    try:
        tous = await get_all_eleves()
    except Exception as e:
        raise HTTPException(502, f"MS2 inaccessible : {e}")

    miens = [e for e in tous if e.get("parentId") == parent_id]
    if not miens:
        return {"sens": sens, "enfants": []}

    # On planifie les groupes concernés (la tournée entière est nécessaire au calcul du cumul),
    # mais on n'en ressort que les étapes des enfants du parent.
    groupes = sorted({e["groupeId"] for e in miens if e.get("groupeId") is not None})
    if not groupes:
        raise HTTPException(409, "Vos enfants ne sont affectés à aucun groupe (clustering MS6 non appliqué)")

    par_groupe = {g: [e for e in tous if e.get("groupeId") == g] for g in groupes}
    resultats = await asyncio.gather(*[planifier(par_groupe[g], sens=sens) for g in groupes])
    plans = dict(zip(groupes, resultats))

    enfants = []
    for e in miens:
        plan = plans.get(e.get("groupeId"))
        if not plan:
            continue
        etape = next((s for s in plan["etapes"] if s["eleveId"] == e["id"]), None)
        if etape is None:
            continue
        enfants.append({
            "eleveId": e["id"], "prenom": e.get("prenom"), "nom": e.get("nom"),
            "groupeId": e.get("groupeId"), "busId": e.get("busId"),
            "rang": etape["rang"], "n_arrets": plan["n_arrets"],
            "cumul_distance_m": etape["cumul_distance_m"],
            "cumul_duree_s": etape["cumul_duree_s"],
            "tournee_duree_min": plan["duree_min"],
            "tournee_distance_m": plan["distance_m"],
        })
    enfants.sort(key=lambda x: x["rang"])
    return {"sens": sens, "enfants": enfants}


@app.post("/api/planification/tournees", dependencies=[Depends(verify_token)])
async def tournees(sens: str = "matin", persister: bool = True):
    """Tournées de tous les groupes (lit l'affectation MS6 courante via MS2). `persister` → écrit l'ordre dans MS2."""
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

    # Calcul des tournées EN PARALLÈLE (OSRM concurrent) — bien plus rapide que séquentiel.
    gs = sorted(groupes)
    results = await asyncio.gather(*[planifier(groupes[g], sens=sens) for g in gs])

    tournees_out, dist_tot, duree_tot = [], 0.0, 0.0
    ordre_global: dict[int, int] = {}
    for g, r in zip(gs, results):
        r["groupeId"] = g
        tournees_out.append(r)
        dist_tot += r["distance_m"]; duree_tot += r["duree_min"]
        for i, eid in enumerate(r.get("ordre", [])):
            ordre_global[int(eid)] = i + 1

    persiste = await assigner_ordre_bulk(ordre_global) if (persister and ordre_global) else 0
    gains = [t["gain_vs_baseline_%"] for t in tournees_out if t["n_arrets"] > 1]
    return {
        "sens": sens,
        "n_bus": len(tournees_out),
        "distance_totale_km": round(dist_tot / 1000.0, 2),
        "duree_totale_min": round(duree_tot, 1),
        "gain_moyen_%": round(sum(gains) / len(gains), 1) if gains else 0.0,
        "ordre_persiste": persiste,
        "tournees": tournees_out,
    }
