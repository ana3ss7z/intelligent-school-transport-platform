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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from clustering import comparer, run_dbscan, run_kmeans
from config import settings
from ms2_client import assigner_groupes_bulk, get_all_eleves, get_eleves_sans_groupe
from rabbitmq import start_consumer

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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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
    """Compare K-Means vs DBSCAN Haversine. JWT ADMIN requis."""
    try:
        eleves = await get_all_eleves()
        return comparer(eleves)
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Helper ───────────────────────────────────────────────────────────

def _distribution(labels: dict[int, int]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for g in labels.values():
        k = f"groupe_{g}"
        dist[k] = dist.get(k, 0) + 1
    return dist