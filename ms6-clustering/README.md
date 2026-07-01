# MS6 — ClusteringService (v2, routier & capacitaire)

Service Python/FastAPI (port 8086) qui regroupe les élèves en **groupes de ramassage faisables pour
un bus**, à partir d'une démarche data science validée dans `notebooks/`.

## Stratégie de production
**k-médoïdes capacitaire sur distance routière OSRM**, avec :
- **Distance réelle** : matrice routière OSRM (réseau de Meknès) — repli euclidien (projection UTM
  30N) si OSRM indisponible. (L'euclidien après `StandardScaler(lat,lon)` est *évité* : il déforme
  la géométrie à 33.9°N.)
- **Capacité garantie** : affectation par **flot à coût minimal** (LP de transport, solution
  entière) → `taille ≤ capacité` par construction.
- **Élèves dispersés** : détectés (bruit DBSCAN), signalés pour ramassage individuel, puis affectés
  au médoïde le plus proche disposant d'une place.
- **Nombre de bus** : choisi par **courbe de Pareto** (qualité/compacité vs flotte), `k ≥ ⌈N/cap⌉`.

## Architecture des modules
| Fichier | Rôle |
|---|---|
| `features.py` | projection UTM (pyproj) + matrices euclidienne / haversine |
| `osrm_client.py` | matrice de distances **routières** OSRM (par blocs, async) |
| `ms1_client.py` | capacités de la flotte (MS1) |
| `algorithms.py` | K-Means, K-Means capacitaire, DBSCAN, **k-médoïdes capacitaire** (min-cost-flow) |
| `evaluation.py` | indices internes + KPI métier (faisabilité, compacité, équilibre) |
| `selection.py` | Pareto sur le nombre de bus + choix de k |
| `clustering.py` | orchestrateur (`production_clustering`, + legacy `run_kmeans/run_dbscan/comparer`) |
| `main.py` | API FastAPI + JWT | 
| `rabbitmq.py` | recalcul auto sur événements élèves |

## Endpoints
| Route | Auth | Description |
|---|---|---|
| `GET /api/clustering/health` | public | health check |
| `GET /api/clustering/eleves` · `/sans-groupe` | public | données MS2 |
| `GET /api/clustering/diagnostics` | public | stats + nb de bus recommandé |
| `POST /api/clustering/production?appliquer=&capacity=&road=` | ADMIN | **stratégie de production** (recommandé) |
| `POST /api/clustering/pareto?capacity=&road=` | ADMIN | courbe de Pareto (sans écrire) |
| `POST /api/clustering/comparer` | ADMIN | K-Means vs DBSCAN (exploratoire) |
| `POST /api/clustering/kmeans` · `/dbscan` | ADMIN | exploratoire (legacy, projeté) |

## Configuration (`.env`)
`BUS_CAPACITY`, `USE_ROAD_DISTANCE`, `USE_ROAD_FOR_AUTO`, `EPSG_METRIC`, `MIN_SILHOUETTE`,
`K_MARGIN`, `OSRM_URL`, `MS1_URL`, `MS2_URL`, `JWT_SECRET` (= `app.jwt.secret` de MS7).

## Démarrage
```bash
pip install -r requirements.txt          # service
docker start osrm_meknes                 # OSRM (sinon repli euclidien automatique)
uvicorn main:app --host 0.0.0.0 --port 8086 --reload
```
Exemple : `POST /api/clustering/production?appliquer=true` → calcule les groupes (routier,
capacitaire), écrit `groupeId` dans MS2 (bulk) et renvoie métriques + Pareto + dispersés.

## Travail data science (`notebooks/`)
1. `clustering_study.ipynb` — EDA / CRISP-DM
2. `02_model_comparison.ipynb` — benchmark de ~11 algorithmes
3. `03_production_strategy.ipynb` — distance routière + capacitaire + Pareto → config de production

Données reproductibles : `data/eleves_meknes.csv` (généré par `seed_eleves_meknes_v2.py`),
`data/osrm_dist_m.npy` (matrice routière en cache). Dépendances notebook : `requirements-notebook.txt`.
