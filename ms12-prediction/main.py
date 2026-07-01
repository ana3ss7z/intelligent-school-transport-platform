"""
MS12 — PredictionService (FastAPI, port 8088)
Prédiction du temps d'arrivée (ETA) d'un trajet de bus scolaire.
Modèle = meilleur régresseur choisi par benchmark (chargé de façon agnostique).
Sécurité : JWT requis sur /predict (ADMIN/CHAUFFEUR). CORS géré uniquement par la Gateway.
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

import jwt
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from config import settings
from model import eta_model
from osrm_client import route_async

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger(__name__)

security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Vérifie le JWT émis par MS7 (même secret). ADMIN ou CHAUFFEUR autorisés."""
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("role", "") not in ("ADMIN", "CHAUFFEUR"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès réservé ADMIN/CHAUFFEUR")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalide")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ok = eta_model.load()
    if ok:
        logger.info("[MS12] Modèle chargé : %s (v%s)",
                    eta_model.config.get("algorithme"), eta_model.config.get("version"))
    else:
        logger.warning("[MS12] Aucun modèle — lancer `python train.py`. /predict renverra 503.")
    yield


app = FastAPI(title="MS12 — PredictionService (ETA)", version="1.0.0", lifespan=lifespan)


# ── Schéma de requête ────────────────────────────────────────────────
class PredictRequest(BaseModel):
    # Option A : coordonnées (OSRM calcule distance/durée) ; Option B : distance/durée fournies
    bus_lat: float | None = None
    bus_lng: float | None = None
    dest_lat: float | None = None
    dest_lng: float | None = None
    distance_routiere_m: float | None = None
    duree_base_s: float | None = None

    moment: str = "matin"                 # matin | soir
    heure_depart: float | None = None      # défaut : 7.5 (matin) / 17.5 (soir)
    jour_semaine: int = 0
    mois: int = 9
    meteo: str = "ensoleille"              # ensoleille|nuageux|pluie|brouillard
    trafic: str = "fluide"                 # fluide|modere|dense|embouteillage
    ramadan: int = 0
    jour_souk: int = 0
    travaux_prevus: int = 0
    traverse_oued: int = 0
    nb_feux: int = 8
    nb_arrets_restants: int = 0
    nb_montees: int = 0
    nb_descentes: int = 0
    taux_occupation: float = 0.0
    retard_cumule_min: float = 0.0
    duree_moyenne_historique_min: float | None = None


# ── Routes ───────────────────────────────────────────────────────────
@app.get("/api/eta/health")
async def health():
    return {"status": "UP", "service": "ms12-prediction", "port": settings.port,
            "model_loaded": eta_model.loaded,
            "algorithme": eta_model.config.get("algorithme")}


@app.get("/api/eta/model-info")
async def model_info():
    if not eta_model.loaded:
        raise HTTPException(503, "Modèle non entraîné — lancer train.py")
    c = eta_model.config
    return {k: c.get(k) for k in
            ("version", "algorithme", "metrics_test", "baseline_osrm_test",
             "gain_vs_baseline_%", "mae_minutes", "n_lignes", "n_features",
             "importances", "dateCalcul")}


@app.post("/api/eta/predict", dependencies=[Depends(verify_token)])
async def predict(req: PredictRequest):
    if not eta_model.loaded:
        raise HTTPException(503, "Modèle non entraîné — lancer train.py")

    dist, dur = req.distance_routiere_m, req.duree_base_s
    if dist is None or dur is None:
        if None in (req.bus_lat, req.bus_lng, req.dest_lat, req.dest_lng):
            raise HTTPException(422, "Fournir (bus_lat,bus_lng,dest_lat,dest_lng) ou (distance_routiere_m,duree_base_s)")
        dur, dist = await route_async(req.bus_lat, req.bus_lng, req.dest_lat, req.dest_lng)

    heure = req.heure_depart if req.heure_depart is not None else (7.5 if req.moment == "matin" else 17.5)
    hist_s = (req.duree_moyenne_historique_min * 60.0
              if req.duree_moyenne_historique_min is not None else dur)

    row = {
        "heure_depart": heure, "moment": req.moment,
        "jour_semaine": req.jour_semaine, "mois": req.mois,
        "meteo": req.meteo, "trafic": req.trafic,
        "ramadan": req.ramadan, "jour_souk": req.jour_souk,
        "travaux_prevus": req.travaux_prevus, "traverse_oued": req.traverse_oued,
        "nb_feux": req.nb_feux, "distance_routiere_m": dist, "duree_base_s": dur,
        "nb_arrets_restants": req.nb_arrets_restants,
        "nb_montees": req.nb_montees, "nb_descentes": req.nb_descentes,
        "taux_occupation": req.taux_occupation,
        "duree_moyenne_historique_s": hist_s,
        "retard_cumule_s": req.retard_cumule_min * 60.0,
    }
    eta_min = float(eta_model.predict_df(pd.DataFrame([row]))[0])
    mae = float(eta_model.config.get("mae_minutes", 0.0))

    arr = heure + eta_min / 60.0
    hh, mm = int(arr) % 24, int(round((arr - int(arr)) * 60)) % 60
    return {
        "eta_minutes": round(eta_min, 2),
        "intervalle_min": [round(max(0, eta_min - mae), 2), round(eta_min + mae, 2)],
        "heure_depart": round(heure, 2),
        "heure_arrivee_estimee": f"{hh:02d}:{mm:02d}",
        "distance_routiere_m": round(dist, 1),
        "duree_base_min": round(dur / 60.0, 2),
        "modele": eta_model.config.get("algorithme"),
        "facteurs": {"meteo": req.meteo, "trafic": req.trafic, "moment": req.moment,
                     "ramadan": req.ramadan, "jour_souk": req.jour_souk,
                     "travaux_prevus": req.travaux_prevus},
    }
