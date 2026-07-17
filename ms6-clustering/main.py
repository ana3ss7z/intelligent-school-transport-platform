"""
MS6 — ClusteringService (FastAPI, port 8086)
Clustering géographique K-Means + DBSCAN Haversine.
Sécurité : JWT requis sur les routes de déclenchement (ADMIN).
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from binding import appliquer_bus
from clustering import (comparer, run_dbscan, run_kmeans,
                        production_clustering, pareto_flotte, diagnostics)
from config import settings
from ms2_client import assigner_groupes_bulk, get_all_eleves, get_eleves_sans_groupe
from quality import charger_baseline, maybe_maj_baseline
from rabbitmq import start_consumer

# Dernier verdict qualité calculé (exposé par GET /api/clustering/quality)
_dernier_verdict: dict | None = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger(__name__)

# ── JWT ──────────────────────────────────────────────────────────────
security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Vérifie le JWT émis par MS7-Auth. Même secret que Spring Boot."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
        )
        # Vérifie que c'est un ADMIN
        role = payload.get("role", "")
        if role != "ADMIN":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux ADMIN")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")


# ── Lifespan ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[MS6] Démarrage ClusteringService — port %d", settings.port)
    asyncio.create_task(start_consumer())
    yield


app = FastAPI(title="MS6 — ClusteringService", version="1.0.0", lifespan=lifespan)
# CORS géré uniquement par la Gateway (MS8) — pas de CORS ici (évite les en-têtes en double)


# ── Routes publiques (pas de JWT) ────────────────────────────────────

@app.get("/api/clustering/health")
async def health():
    return {"status": "UP", "service": "ms6-clustering", "port": settings.port}


@app.get("/api/clustering/eleves")
async def liste_eleves():
    """Lecture seule — pas de JWT requis."""
    try:
        eleves = await get_all_eleves()
        return {"total": len(eleves), "eleves": eleves}
    except Exception as e:
        raise HTTPException(502, f"MS2 inaccessible : {e}")


@app.get("/api/clustering/sans-groupe")
async def eleves_sans_groupe():
    try:
        eleves = await get_eleves_sans_groupe()
        return {"total": len(eleves), "eleves": eleves}
    except Exception as e:
        raise HTTPException(502, f"MS2 inaccessible : {e}")


@app.get("/api/clustering/diagnostics")
async def clustering_diagnostics():
    """Stats EDA rapides + nombre de bus recommandé. Lecture seule."""
    try:
        eleves = await get_all_eleves()
        return diagnostics(eleves)
    except Exception as e:
        raise HTTPException(502, f"MS2 inaccessible : {e}")


@app.get("/api/clustering/quality")
async def clustering_quality():
    """Garde-fou qualité : référence dynamique + seuils + dernier verdict calculé. Lecture seule.
    Destiné au dashboard admin (UC-13). Le seuil est RELATIF (pas un 0.5 fixe)."""
    return {
        "baseline": charger_baseline(),
        "dernier_verdict": _dernier_verdict,
        "seuils": {
            "sil_drop_rel": settings.quality_sil_drop_rel,
            "sil_drop_abs": settings.quality_sil_drop_abs,
            "sil_floor_rel": settings.quality_sil_floor_rel,
            "comp_inc_rel": settings.quality_comp_inc_rel,
            "disperses_inc": settings.quality_disperses_inc,
        },
        "note": "Référence calibrée sur nos runs réels (~0.43), pas sur un seuil générique 0.5.",
    }


# ── Routes protégées (JWT ADMIN requis) ──────────────────────────────

@app.post("/api/clustering/kmeans", dependencies=[Depends(verify_token)])
async def clustering_kmeans(appliquer: bool = True):
    """K-Means (k=3..5, meilleur Silhouette). JWT ADMIN requis."""
    try:
        eleves = await get_all_eleves()
        result = run_kmeans(eleves)
        updated = await assigner_groupes_bulk(result.labels) if appliquer else "non demandé"
        return {
            "methode": "kmeans",
            "k": result.k,
            "silhouette": result.silhouette,
            "nb_eleves": len(result.labels),
            "groupes_appliques": updated,
            "distribution": _distribution(result.labels),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/clustering/dbscan", dependencies=[Depends(verify_token)])
async def clustering_dbscan(appliquer: bool = False):
    """DBSCAN Haversine. JWT ADMIN requis."""
    try:
        eleves = await get_all_eleves()
        result = run_dbscan(eleves)
        updated = await assigner_groupes_bulk(result.labels) if appliquer else "non demandé"
        return {
            "methode": "dbscan",
            "k": result.k,
            "silhouette": result.silhouette,
            "nb_eleves": len(result.labels),
            "groupes_appliques": updated,
            "distribution": _distribution(result.labels),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/clustering/comparer", dependencies=[Depends(verify_token)])
async def comparer_algorithmes():
    """Compare K-Means vs DBSCAN (espace métrique projeté). JWT ADMIN requis."""
    try:
        eleves = await get_all_eleves()
        return comparer(eleves)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/clustering/production", dependencies=[Depends(verify_token)])
async def clustering_production(appliquer: bool = True,
                                capacity: int | None = None,
                                road: bool | None = None,
                                rayon: float | None = None):
    """
    Stratégie de production : k-médoïdes capacitaire sur distance routière OSRM (repli euclidien),
    détection des dispersés, choix du nombre de bus par Pareto. JWT ADMIN requis.
    `capacity` et `rayon` (distance max élève→médoïde, m ; 0 = désactivé) sont ajustables.
    """
    global _dernier_verdict
    try:
        eleves = await get_all_eleves()
        result = await production_clustering(eleves, capacity=capacity, use_road=road, rayon=rayon)
        updated = await assigner_groupes_bulk(result.labels) if appliquer else "non demandé"

        # Liaison groupe↔bus : propage busId (rend notifs MS4 / ETA MS12 fonctionnels)
        bus_binding = await appliquer_bus(result.labels) if appliquer else "non demandé"

        # Garde-fou qualité : verdict informatif ; baseline MAJ seulement si run appliqué ET OK
        verdict = result.extra["quality"]
        _dernier_verdict = verdict
        if verdict["niveau"] != "OK":
            logger.warning("[MS6] Qualité clustering %s : %s", verdict["niveau"], "; ".join(verdict["raisons"]))
            from rabbitmq import signaler_qualite
            await signaler_qualite(result)              # canal admin (D1)
        if appliquer:
            maybe_maj_baseline(result.metrics, result.extra, verdict)

        return {
            "methode": result.methode,
            "k": result.k,
            "silhouette": result.silhouette,
            "nb_eleves": len(result.labels),
            "groupes_appliques": updated,
            "bus_binding": bus_binding,
            "distance": result.extra["distance"],
            "capacity": result.extra["capacity"],
            "rayon_max_m": result.extra["rayon_max_m"],
            "n_disperses": result.extra["n_disperses"],
            "disperses_ids": result.extra["disperses_ids"],
            "n_non_affectes": result.extra["n_non_affectes"],
            "non_affectes_ids": result.extra["non_affectes_ids"],
            "metrics": result.metrics,
            "quality": verdict,
            "pareto": result.extra["pareto"],
            "distribution": _distribution(result.labels),
            "assignments": result.labels,   # {eleveId: groupe} → prévisualisation carte (même non appliqué)
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/clustering/pareto", dependencies=[Depends(verify_token)])
async def clustering_pareto(capacity: int | None = None, road: bool | None = None,
                            rayon: float | None = None):
    """Courbe de Pareto qualité/compacité vs nombre de bus (sans appliquer). JWT ADMIN requis."""
    try:
        eleves = await get_all_eleves()
        return await pareto_flotte(eleves, capacity=capacity, use_road=road, rayon=rayon)
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Helper ───────────────────────────────────────────────────────────

def _distribution(labels: dict[int, int]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for g in labels.values():
        k = f"groupe_{g}"
        dist[k] = dist.get(k, 0) + 1
    return dist