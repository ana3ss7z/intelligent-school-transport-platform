"""
MS11 — AnalytiqueService (FastAPI, port 8091)
Détection d'anomalies sur les trajets de bus (Isolation Forest, non supervisé).
Sécurité : JWT ADMIN. CORS géré uniquement par la Gateway.
"""
from __future__ import annotations
import json
import logging
import os
from contextlib import asynccontextmanager

import jwt
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from config import settings
from anomaly import AnomalyDetector
from features import label_binaire
from osrm_client import route_async

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger(__name__)

security = HTTPBearer()

_state: dict = {"detector": None, "config": {}}


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("role", "") != "ADMIN":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès réservé aux ADMIN")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalide")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.path.exists(settings.model_path) and os.path.exists(settings.config_path):
        _state["detector"] = AnomalyDetector.load(settings.model_path)
        with open(settings.config_path, encoding="utf-8") as f:
            _state["config"] = json.load(f)
        logger.info("[MS11] Détecteur chargé : %s (v%s)",
                    _state["config"].get("detecteur"), _state["config"].get("version"))
    else:
        logger.warning("[MS11] Aucun modèle — lancer `python train_anomaly.py`.")
    yield


app = FastAPI(title="MS11 — AnalytiqueService (anomalies)", version="1.0.0", lifespan=lifespan)


def _loaded() -> bool:
    return _state["detector"] is not None


def _niveau(is_anom: bool, ratio: float) -> str:
    if not is_anom:
        return "normal"
    return "critique" if ratio >= 3.0 else "suspect"


# ── Schéma ───────────────────────────────────────────────────────────
class AnomalyRequest(BaseModel):
    duree_reelle_min: float                 # durée OBSERVÉE du trajet (requis)
    duree_base_s: float | None = None       # ou coordonnées → OSRM
    bus_lat: float | None = None
    bus_lng: float | None = None
    dest_lat: float | None = None
    dest_lng: float | None = None
    moment: str = "matin"
    meteo: str = "ensoleille"
    trafic: str = "fluide"
    distance_routiere_m: float | None = None
    retard_cumule_min: float = 0.0
    nb_montees: int = 0
    nb_descentes: int = 0
    taux_occupation: float = 0.0
    nb_arrets_restants: int = 0
    nb_feux: int = 8
    traverse_oued: int = 0
    ramadan: int = 0
    jour_souk: int = 0
    travaux_prevus: int = 0


# ── Routes ───────────────────────────────────────────────────────────
@app.get("/api/analytique/health")
async def health():
    return {"status": "UP", "service": "ms11-analytique", "port": settings.port,
            "model_loaded": _loaded(), "detecteur": _state["config"].get("detecteur")}


@app.get("/api/analytique/model-info")
async def model_info():
    if not _loaded():
        raise HTTPException(503, "Modèle non entraîné — lancer train_anomaly.py")
    c = _state["config"]
    return {k: c.get(k) for k in
            ("version", "detecteur", "approach", "with_outcome", "threshold", "contamination",
             "metrics_test", "n_trajets", "taux_incidents_%", "dateCalcul")}


@app.post("/api/analytique/anomalies", dependencies=[Depends(verify_token)])
async def detecter(req: AnomalyRequest):
    if not _loaded():
        raise HTTPException(503, "Modèle non entraîné — lancer train_anomaly.py")

    dur = req.duree_base_s
    dist = req.distance_routiere_m or 0.0
    if dur is None:
        if None in (req.bus_lat, req.bus_lng, req.dest_lat, req.dest_lng):
            raise HTTPException(422, "Fournir duree_base_s ou les coordonnées (bus + destination)")
        dur, dist = await route_async(req.bus_lat, req.bus_lng, req.dest_lat, req.dest_lng)

    row = {
        "duree_reelle_min": req.duree_reelle_min, "duree_base_s": dur,
        "distance_routiere_m": dist, "retard_cumule_s": req.retard_cumule_min * 60.0,
        "nb_montees": req.nb_montees, "nb_descentes": req.nb_descentes,
        "taux_occupation": req.taux_occupation, "nb_arrets_restants": req.nb_arrets_restants,
        "nb_feux": req.nb_feux, "traverse_oued": req.traverse_oued,
        "ramadan": req.ramadan, "jour_souk": req.jour_souk, "travaux_prevus": req.travaux_prevus,
        "moment": req.moment, "meteo": req.meteo, "trafic": req.trafic,
    }
    df = pd.DataFrame([row])
    det = _state["detector"]
    score = float(det.scores(df)[0])
    is_anom = bool(score >= det.threshold)
    ratio = req.duree_reelle_min * 60.0 / max(1.0, dur)
    return {
        "is_anomaly": is_anom,
        "anomaly_score": round(score, 4),
        "seuil": round(float(det.threshold), 4),
        "ratio_reel_base": round(ratio, 2),
        "niveau": _niveau(is_anom, ratio),
        "detecteur": _state["config"].get("detecteur"),
    }


@app.get("/api/analytique/anomalies/scan", dependencies=[Depends(verify_token)])
async def scan(limit: int = 20):
    if not _loaded():
        raise HTTPException(503, "Modèle non entraîné — lancer train_anomaly.py")
    if not os.path.exists(settings.eta_dataset_path):
        raise HTTPException(502, "Dataset ETA introuvable")

    df = pd.read_csv(settings.eta_dataset_path)
    det = _state["detector"]
    scores = det.scores(df)
    preds = scores >= det.threshold
    reel = label_binaire(df).to_numpy().astype(bool)

    detectes = int(preds.sum())
    tp = int((preds & reel).sum())
    precision = round(tp / detectes, 3) if detectes else 0.0
    rappel = round(tp / int(reel.sum()), 3) if reel.sum() else 0.0

    df = df.assign(_score=scores, _anom=preds)
    top = df.sort_values("_score", ascending=False).head(limit)
    anomalies = [{
        "date": r["date"], "circuit_id": int(r["circuit_id"]), "moment": r["moment"],
        "leg_id": int(r["leg_id"]),
        "duree_reelle_min": round(float(r["duree_reelle_min"]), 2),
        "duree_base_min": round(float(r["duree_base_s"]) / 60.0, 2),
        "ratio": round(float(r["duree_reelle_min"]) * 60.0 / max(1.0, float(r["duree_base_s"])), 2),
        "score": round(float(r["_score"]), 4),
        "is_anomaly": bool(r["_anom"]),
        "incident_reel": r["incident_type"],   # vérité terrain (pour comparaison)
    } for _, r in top.iterrows()]

    return {
        "n_trajets": len(df),
        "n_detectees": detectes,
        "n_incidents_reels": int(reel.sum()),
        "precision": precision,
        "rappel": rappel,
        "top_anomalies": anomalies,
    }
