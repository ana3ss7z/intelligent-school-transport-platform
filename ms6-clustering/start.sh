#!/bin/bash
# ── Démarrer MS6 ClusteringService ───────────────────────────────────

echo "📦 Installation des dépendances..."
pip install -r requirements.txt

echo "🚀 Démarrage MS6 sur port 8086..."
uvicorn main:app --host 0.0.0.0 --port 8086 --reload

# ─────────────────────────────────────────────────────────────────────
# Tests rapides (dans un autre terminal une fois MS6 démarré)
# ─────────────────────────────────────────────────────────────────────

# 1. Health check
# curl http://localhost:8086/api/clustering/health

# 2. Comparer K-Means vs DBSCAN (sans écrire dans MS2)
# curl -X POST http://localhost:8086/api/clustering/comparer | python -m json.tool

# 3. Lancer K-Means ET écrire les groupeId dans MS2
# curl -X POST "http://localhost:8086/api/clustering/kmeans?appliquer=true" | python -m json.tool

# 4. Voir les élèves sans groupe (après reset)
# curl http://localhost:8086/api/clustering/sans-groupe | python -m json.tool

# 5. Docs Swagger automatiques
# http://localhost:8086/docs
