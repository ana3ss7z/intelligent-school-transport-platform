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

from datetime import date as _date

from config import settings
from model import eta_model
from osrm_client import route_async
from context import weather, traffic, calendar_ma, roster_ms2, history
from context import circuits as circuits_ctx

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger(__name__)

security = HTTPBearer()


def _hhmm(heure_decimale: float) -> str:
    """Heure décimale (ex. 7.5) → 'HH:MM' (ex. '07:30'). Gère le report des minutes."""
    total = int(round(heure_decimale * 60)) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


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

    # Contexte du trajet (sert à l'auto-approvisionnement des features)
    moment: str = "matin"                 # matin | soir
    heure_depart: float | None = None      # défaut : 7.5 (matin) / 17.5 (soir)
    date: str | None = None                # ISO (YYYY-MM-DD) ; défaut : aujourd'hui
    circuit_id: int | None = None
    leg_id: int | None = None
    bus_id: int | None = None
    auto_context: bool = True              # remplit automatiquement les features non fournies

    # Features : si None ET auto_context → approvisionnées par context/* ; sinon défaut neutre
    jour_semaine: int | None = None
    mois: int | None = None
    meteo: str | None = None
    trafic: str | None = None
    ramadan: int | None = None
    jour_souk: int | None = None
    travaux_prevus: int | None = None
    traverse_oued: int | None = None
    nb_feux: int | None = None
    nb_arrets_restants: int | None = None
    nb_montees: int | None = None
    nb_descentes: int | None = None
    taux_occupation: float | None = None
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
    """
    Prédit l'ETA d'un tronçon. Avec `auto_context=true`, chaque feature non fournie est
    **approvisionnée automatiquement** depuis sa source réelle (OSRM, Open-Meteo, calendrier,
    table circuits, roster MS2, historique). Le bloc `sources` indique la provenance de chaque valeur.
    """
    if not eta_model.loaded:
        raise HTTPException(503, "Modèle non entraîné — lancer train.py")

    auto = req.auto_context
    sources: dict[str, str] = {}

    # ── Distance / durée de base (OSRM) ──
    dist, dur = req.distance_routiere_m, req.duree_base_s
    if dist is None or dur is None:
        if None in (req.bus_lat, req.bus_lng, req.dest_lat, req.dest_lng):
            raise HTTPException(422, "Fournir (bus_lat,bus_lng,dest_lat,dest_lng) ou (distance_routiere_m,duree_base_s)")
        dur, dist = await route_async(req.bus_lat, req.bus_lng, req.dest_lat, req.dest_lng)
        sources["distance/duree"] = "OSRM"
    else:
        sources["distance/duree"] = "fournis"

    # ── Contexte temporel ──
    date_obj = _date.fromisoformat(req.date) if req.date else _date.today()
    heure = req.heure_depart if req.heure_depart is not None else (7.5 if req.moment == "matin" else 17.5)
    jour_semaine = req.jour_semaine if req.jour_semaine is not None else date_obj.weekday()
    mois = req.mois if req.mois is not None else date_obj.month

    def _resolu(val, defaut, src_auto, cle):
        """Renvoie val si fournie ; sinon auto (marque la source) ou défaut neutre."""
        if val is not None:
            sources[cle] = "fourni"
            return val
        if auto:
            sources[cle] = src_auto[1]
            return src_auto[0]
        return defaut

    # ── Calendrier (ramadan / souk) ──
    ramadan = _resolu(req.ramadan, 0, (calendar_ma.est_ramadan(date_obj), "calendrier"), "ramadan")
    jour_souk = _resolu(req.jour_souk, 0, (calendar_ma.jour_souk(date_obj), "calendrier"), "jour_souk")
    travaux_prevus = req.travaux_prevus if req.travaux_prevus is not None else 0

    # ── Attributs statiques du circuit ──
    attrs = circuits_ctx.circuit_attrs(req.circuit_id) if (auto and req.circuit_id) else {}
    nb_feux = _resolu(req.nb_feux, 8, (attrs.get("nb_feux", 8), "table circuits"), "nb_feux")
    traverse_oued = _resolu(req.traverse_oued, 0, (attrs.get("traverse_oued", 0), "table circuits"), "traverse_oued")
    nar_auto = (circuits_ctx.nb_arrets_restants(req.circuit_id, req.leg_id)
                if (auto and req.circuit_id and req.leg_id is not None) else 0)
    nb_arrets_restants = _resolu(req.nb_arrets_restants, 0, (nar_auto, "table circuits"), "nb_arrets_restants")

    # ── Météo (Open-Meteo) ──
    if req.meteo is not None:
        meteo = req.meteo; sources["meteo"] = "fournie"
    elif auto:
        lat = req.bus_lat if req.bus_lat is not None else (req.dest_lat if req.dest_lat is not None else circuits_ctx.ECOLE["lat"])
        lng = req.bus_lng if req.bus_lng is not None else (req.dest_lng if req.dest_lng is not None else circuits_ctx.ECOLE["lng"])
        meteo, src = await weather.get_meteo(lat, lng, mois); sources["meteo"] = src
    else:
        meteo = "ensoleille"

    # ── Trafic (heuristique horaire) ──
    if req.trafic is not None:
        trafic_cat = req.trafic; sources["trafic"] = "fourni"
    elif auto:
        trafic_cat, src = traffic.get_trafic(heure, jour_semaine); sources["trafic"] = src
    else:
        trafic_cat = "fluide"

    # ── Occupation / dwell (roster MS2) ──
    if auto and req.bus_id and (req.nb_montees is None or req.nb_descentes is None or req.taux_occupation is None):
        n_arrets = circuits_ctx.n_legs(circuits_ctx.CIRCUITS[req.circuit_id]) if req.circuit_id in circuits_ctx.CIRCUITS else 4
        occ, src = await roster_ms2.get_occupation(req.bus_id, req.moment, req.leg_id or 0, n_arrets)
        sources["occupation"] = src
    else:
        occ = {}
    nb_montees = req.nb_montees if req.nb_montees is not None else occ.get("nb_montees", 0)
    nb_descentes = req.nb_descentes if req.nb_descentes is not None else occ.get("nb_descentes", 0)
    taux_occupation = req.taux_occupation if req.taux_occupation is not None else occ.get("taux_occupation", 0.0)

    # ── Historique (cold-start → OSRM) ──
    if req.duree_moyenne_historique_min is not None:
        hist_s = req.duree_moyenne_historique_min * 60.0; sources["historique"] = "fourni"
    elif auto:
        hist_s, src = history.get_duree_moyenne_historique(req.circuit_id, req.moment, req.leg_id, dur)
        sources["historique"] = src
    else:
        hist_s = dur

    row = {
        "heure_depart": heure, "moment": req.moment,
        "jour_semaine": jour_semaine, "mois": mois,
        "meteo": meteo, "trafic": trafic_cat,
        "ramadan": ramadan, "jour_souk": jour_souk,
        "travaux_prevus": travaux_prevus, "traverse_oued": traverse_oued,
        "nb_feux": nb_feux, "distance_routiere_m": dist, "duree_base_s": dur,
        "nb_arrets_restants": nb_arrets_restants,
        "nb_montees": nb_montees, "nb_descentes": nb_descentes,
        "taux_occupation": taux_occupation,
        "duree_moyenne_historique_s": hist_s,
        "retard_cumule_s": req.retard_cumule_min * 60.0,
    }
    eta_min = float(eta_model.predict_df(pd.DataFrame([row]))[0])
    mae = float(eta_model.config.get("mae_minutes", 0.0))

    return {
        "eta_minutes": round(eta_min, 2),
        "intervalle_min": [round(max(0, eta_min - mae), 2), round(eta_min + mae, 2)],
        "heure_depart": _hhmm(heure),
        "heure_depart_dec": round(heure, 2),
        "heure_arrivee_estimee": _hhmm(heure + eta_min / 60.0),
        "date": date_obj.isoformat(),
        "distance_routiere_m": round(dist, 1),
        "duree_base_min": round(dur / 60.0, 2),
        "modele": eta_model.config.get("algorithme"),
        "contexte_auto": auto,
        "facteurs": {"meteo": meteo, "trafic": trafic_cat, "moment": req.moment,
                     "ramadan": ramadan, "jour_souk": jour_souk, "travaux_prevus": travaux_prevus},
        "sources": sources,
    }
