# CLAUDE.md — Transport Scolaire Intelligent
## État au 1er juillet 2026 — S7 (MS6 clustering v3) + S8 en cours (MS12 prédiction ETA)

---

## 🎯 Résumé du projet

Système de transport scolaire intelligent basé sur une architecture **microservices Spring Boot + Python FastAPI**, développé dans le cadre d'un **PFE Master SDIA (M2)**. Le projet digitalise et optimise le transport des élèves à **Meknès, Maroc** (300 élèves seedés avec coordonnées GPS réelles).

> **Données en base = v2** (`seed_eleves_meknes_v2.sql`, chargé via TRUNCATE RESTART IDENTITY → ids 1..300) :
> 6 zones / ~20 secteurs, **destination école** (Al Massira, 33.893/-5.5455), **oued** séparateur, **5 % dispersés**.
> Cohérent avec les notebooks MS6, le CSV `ms6-clustering/data/eleves_meknes.csv` et la matrice OSRM cachée.
> *(v1 `seed_eleves_meknes.sql` = ancien jeu, remplacé.)*

**Étudiant :** Anass  
**Encadrant :** Pr. Ali Bekri  
**Faculté :** Faculté des Sciences Moulay Ismail, Meknès  
**Planning :** S1 à S15 (mai → août 2026)  
**État actuel :** S7 complétée (26 juin 2026) — S8 à démarrer

---

## 📁 Structure racine du projet

```
C:\Users\Anass\Desktop\SDIA\S9\PFE\transport-scolaire\
├── pom.xml                          ← Parent Maven multi-module
├── docker-compose.yml               ← PostgreSQL + Redis + RabbitMQ + pgAdmin
├── .env                             ← Variables d'environnement Docker
├── scripts/init.sql                 ← Init SQL PostgreSQL
├── osrm-data/                       ← Données OSM Maroc pré-processées (OSRM)
├── seed_eleves_meknes.py            ← Script seeding 300 élèves
├── seed_eleves_meknes.sql           ← SQL généré : 300 élèves Meknès
├── simulateur-bus/
│   └── bus_simulator.py            ← Simulateur 3 bus Python (OSRM + WebSocket)
├── ws-test/
│   ├── test-gps.html               ← Test WebSocket GPS MS3
│   ├── map-gps.html                ← Carte Leaflet temps réel (GPS + OSRM routes)
│   ├── test-incidents-notifications.html  ← Test flow MS10→MS4 ✅ validé
│   └── test_ms6.html               ← Test clustering MS6 (nouveau S7)
├── ms-common/                       ← Module partagé (JWT, UserPrincipal, Role)
├── ms1-bus/                         ← BusService (port 8081)
├── ms2-eleves/                      ← EleveService (port 8082)
├── ms3-localisation/                ← LocalisationService GPS + WebSocket (port 8083)
├── ms4-notifications/               ← NotificationService FCM (port 8084)
├── ms6-clustering/                  ← ClusteringService FastAPI Python (port 8086) ← NOUVEAU S7
├── ms7-auth/                        ← AuthService JWT (port 8087)
├── ms8-gateway/                     ← API Gateway Spring Cloud (port 8080)
└── ms10-incidents/                  ← IncidentService (port 8090)
```

---

## 🔧 Stack technique

| Catégorie | Technologie |
|-----------|------------|
| **Langage Java** | Java 21 |
| **Framework Java** | Spring Boot 3.5 |
| **Build** | Maven multi-module |
| **Gateway** | Spring Cloud Gateway WebFlux 2024.0.1 |
| **Base de données** | PostgreSQL 15 + PostGIS |
| **Cache** | Redis 7 (rate limiting Gateway + cache GPS) |
| **Messaging** | RabbitMQ 3 (TopicExchange `transport.exchange`) |
| **Sécurité** | JWT HMAC-SHA256 (JJWT 0.12.3), Spring Security 6 |
| **Notifications** | Firebase Admin SDK 9.2.0 (FCM HTTP v1, mode dégradé) |
| **WebSocket** | Spring WebSocket natif (pas STOMP) |
| **GPS routing** | OSRM local (données OSM Maroc) |
| **Langage Python** | Python 3.11+ (3.13 supporté avec libs à jour) |
| **Framework Python** | FastAPI 0.111 + Uvicorn |
| **ML clustering** | scikit-learn 1.5.2, numpy 2.1 |
| **HTTP async** | httpx 0.27 |
| **Messaging Python** | aio-pika 9.4 |
| **Résilience** | Tenacity 8.2.3 (retry exponentiel) |
| **Sécurité Python** | PyJWT 2.8 + cryptography 42 |
| **Tests** | Newman (Postman CLI) : 88/88 assertions ✅ |
| **Conteneurs** | Docker + Docker Compose |

---

## 🏗️ Architecture microservices — État S7

### ms-common (module partagé, PAS de Spring)
- `Role.java` → enum : `ADMIN`, `CHAUFFEUR`, `PARENT`
- `JwtUtils.java` → Java pur, instancié via `@Bean` dans chaque MS
  - Clé : `Base64.getEncoder().encodeToString(secret.getBytes())` + `Decoders.BASE64.decode()`
  - Méthodes : `isTokenValid()`, `extractEmail()`, `extractRole()`, `extractUserId()`
- `UserPrincipal.java` → `email`, `role`, `userId`

**Règle critique :** JwtUtils jamais `@Component`, toujours `@Bean` :
```java
@Bean public JwtUtils jwtUtils() { return new JwtUtils(jwtSecret); }
```

---

### MS7 — AuthService (port 8087) ✅
- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/validate`
- Réponse login : `{ token, userId, nom, email, role }`
- Token JWT contient : `sub` (email), `role`, `userId`, `nom`, `iat`, `exp` (24h)
- CORS supprimé (géré uniquement MS8)

---

### MS1 — BusService (port 8081) ✅
- Entité `Bus` : `id`, `matricule` (unique), `capacite`, `statut`, `chauffeurId`, `latitude`, `longitude`
- `StatutBus` : `ACTIF`, `INACTIF`, `EN_PANNE`
- Endpoints CRUD complets + `PATCH /statut` + `PATCH /position`
- **`GET /api/bus/actifs`** (permitAll, interne) → flotte ACTIF pour la **liaison groupe↔bus** (MS6) ← NOUVEAU B1
- **RabbitMQ publie :** `bus.created`, `bus.deleted` → **déclenche le recalcul clustering MS6** (changement de flotte = changement de capacité totale → `k` peut changer). Config : `spring-boot-starter-amqp` + `RabbitMQConfig` (exchange `transport.exchange`).

---

### MS2 — EleveService (port 8082) ✅ mis à jour S7

**Entité `Eleve` :**
```java
private Long id;
private String nom, prenom;
private Double latitude, longitude;
private Long parentId;   // FK logique vers MS7 (pas de contrainte SQL)
private Long busId;      // FK logique vers MS1 — assigné par ADMIN ou clustering
private Long groupeId;   // Résultat clustering MS6 (K-Means / DBSCAN)
private Boolean statutPresence;
```

**Endpoints complets :**
| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| POST | `/api/eleves` | ADMIN | Créer |
| GET | `/api/eleves` | JWT | Lister tous |
| GET | `/api/eleves/{id}` | JWT | Par ID |
| GET | `/api/eleves/parent/{parentId}` | JWT | Par parent |
| GET | `/api/eleves/groupe/{groupeId}` | JWT | Par groupe |
| GET | `/api/eleves/sans-groupe` | **permitAll** | Sans groupe (MS6) |
| GET | `/api/eleves/bus/{busId}/parents` | **permitAll** | ParentIds par bus (MS4) |
| PUT | `/api/eleves/{id}` | ADMIN | Modifier complet |
| PATCH | `/api/eleves/{id}/bus?busId=X` | ADMIN | Assigner bus |
| PATCH | `/api/eleves/{id}/groupe?groupeId=X` | **permitAll** | Assigner groupe (MS6) |
| PUT | `/api/eleves/groupes/bulk` | **permitAll** | Bulk update groupeId (MS6) ← NOUVEAU |
| PUT | `/api/eleves/bus/bulk` | **permitAll** | Bulk update busId — **liaison groupe↔bus (MS6)** ← NOUVEAU B1 |
| PATCH | `/api/eleves/{id}/presence` | ADMIN/CHAUFFEUR | Présence |
| DELETE | `/api/eleves/{id}` | ADMIN | Supprimer |

**SecurityConfig — routes internes sans JWT :**
```java
.requestMatchers(HttpMethod.GET,  "/api/eleves/bus/*/parents").permitAll()
.requestMatchers(HttpMethod.GET,  "/api/eleves/sans-groupe").permitAll()
.requestMatchers(HttpMethod.PATCH,"/api/eleves/*/groupe").permitAll()
.requestMatchers(HttpMethod.PUT,  "/api/eleves/groupes/bulk").permitAll()
.requestMatchers(HttpMethod.PUT,  "/api/eleves/bus/bulk").permitAll()   // liaison groupe↔bus (B1)
```

**RabbitMQ publie :** `eleve.created`, `eleve.gps.updated`, `eleve.deleted`

**Repository :**
```java
List<Eleve> findByParentId(Long parentId);
List<Eleve> findByBusId(Long busId);
List<Eleve> findByGroupeId(Long groupeId);
List<Eleve> findByGroupeIdIsNull();
```

---

### MS3 — LocalisationService (port 8083) ✅
- WebSocket : `ws://localhost:8083/ws/gps`
- Abonnement : `{"subscribe": "ALL"}` ou `{"subscribe": "BUS:5"}`
- Cache Redis : clé `gps:BUS:5` (TTL 2h)
- RabbitMQ publie : `gps.bus.updated`, `gps.eleve.updated`
- OSRM routing intégré

---

### MS4 — NotificationService (port 8084) ✅ mis à jour S7

**Entité `Notification` (inner enums) :**
```java
public enum TypeNotification {
    INCIDENT_SIGNALE, INCIDENT_RESOLU, BUS_ARRIVE_ECOLE, BUS_EN_ROUTE, RETARD, ENFANT_A_BORD
}
public enum StatutEnvoi { EN_ATTENTE, ENVOYE, ECHEC }
```

**Champs :** `id`, `type`, `statutEnvoi`, `parentId`, `fcmToken`, `titre`, `message`, `sourceId`, `sourceType`, `dateEnvoi`, `erreurFcm`

**Entité `DeviceToken` :** `parentId`, `fcmToken`, `plateforme` (défaut "ANDROID"), `dateEnregistrement`, `actif`

**Endpoints :**
| Route | Auth | Description |
|-------|------|-------------|
| `POST /api/notifications/device-token` | PARENT | Enregistrer token FCM |
| `DELETE /api/notifications/device-token/{token}` | PARENT | Désactiver token |
| `GET /api/notifications/mes-notifications` | PARENT | Historique personnel |
| `GET /api/notifications` | ADMIN | Toutes les notifs |
| `GET /api/notifications/stats` | ADMIN | Stats globales |

**Repository — méthode clé bugfix :**
```java
long countByStatutEnvoi(Notification.StatutEnvoi statut);  // bugfix echecs=0
```

**NotificationService — méthodes :**
- `enregistrerToken(Long parentId, DeviceTokenRequest req)`
- `supprimerToken(String fcmToken)`
- `getMesNotifications(Long parentId)` → `List<NotificationResponse>`
- `getToutesNotifications()` → `List<NotificationResponse>`
- `getStats()` → `Map<String, Long>` (total, envoyes, echecs, attente)
- `envoyerAuParent(Long, TypeNotification, String, String, Long, String)`

**FcmService.envoyerAuParent signature exacte :**
```java
public void envoyerAuParent(Long parentId, TypeNotification type,
                             String titre, String message,
                             Long sourceId, String sourceType)
```

**RabbitMQ consumers :**
- `ms4.incident.signale.queue` → `incident.signale`
- `ms4.incident.resolu.queue` → `incident.resolu`
- `ms4.gps.bus.updated.queue` → `gps.bus.updated` (arrivée école à ≤150 m → `BUS_ARRIVE_ECOLE`)
- `ms4.eta.arriving.queue` → `eta.bus.arriving` (MS12) → « le bus arrive dans ~10 min » (`BUS_EN_ROUTE`, UC-4) ← **NOUVEAU G1**
- `ms4.eleve.presence.queue` → `eleve.presence.updated` (MS2) → « enfant à bord » (`ENFANT_A_BORD`, UC-4) au parent précis ← **NOUVEAU G5**

**Statut FCM :** mode dégradé (placeholder JSON) — ECHEC en DB, fonctionnel dès vrai `firebase-service-account.json`

**Test validé :** flow MS10→RabbitMQ→MS4 ✅ — 6 notifications en DB, stats `echecs: 6` correct (bugfix validé)

---

### MS6 — ClusteringService (port 8086) ✅ refonte data-science « expert » v3

**Technologie :** Python 3.11+ / FastAPI. Pipeline reproductible, géographiquement correct et
**conscient de la capacité des bus** (≠ simple appel sklearn).

**Modèle de PRODUCTION final :** **k-médoïdes capacitaire sur distance routière OSRM** (repli euclidien).
Pipeline en 3 étapes dans `clustering.py::production_clustering` :
1. **Dispersés** — DBSCAN sur la matrice de distances détecte les élèves isolés (signalés pour ramassage individuel).
2. **Nombre de bus** — courbe de **Pareto** (qualité vs nb de bus) sur le cœur ; `k_min = ⌈N/capacité⌉`.
3. **Affectation globale capacitaire** — problème de transport (LP / min-cost-flow, `scipy.optimize.linprog`)
   de TOUS les élèves aux médoïdes → **taille ≤ capacité garantie par construction**. Les dispersés sont
   affectés au médoïde le plus proche (pas de groupe 999 en production).

**Rigueur géographique :** projection **UTM Zone 30N (EPSG:32630, `pyproj`)** → coordonnées en **mètres**
(remplace `StandardScaler(lat,lon)` qui fausse la géométrie à 33.9°N). Silhouette/compacité interprétables en mètres.

**Capacité = paramètre métier uniforme** (tous les bus de même taille, **taille modifiable**) :
`capacity` (query param) → sinon `settings.bus_capacity` (`.env`, défaut **50**). Le nombre de bus s'adapte
automatiquement (`k = ⌈N/capacité⌉` + Pareto). *(Flotte hétérogène = évolution S8, `ms1_client.get_capacites()` prêt mais non branché.)*

**2ᵉ paramètre métier AJUSTABLE — `rayon` (S10) :** distance routière **max élève→médoïde** (m ; `0` = désactivé).
`rayon` (query param) → sinon `settings.rayon_max_m` (`.env`). Contrainte **dure** (SLA compacité) : arcs > R
interdits dans le LP ; les élèves sans bus à ≤ R deviennent **non affectés → groupe 999** (ramassage individuel) ;
repli glouton si LP infaisable. **Arbitrage mesuré** (notebook `06_rayon_max_study.ipynb`) : R↓ ⇒ compacité
garantie ↑ & silhouette cœur ↑, **au prix de** plus de bus et/ou plus de dispersés (ex. R=1500 → compacité_max≤1500, ~3 dispersés ; R=1000 → ~40 dispersés, silhouette 0.57).

**Fichiers (refonte modulaire) :**
```
ms6-clustering/
├── main.py           ← FastAPI app + JWT, endpoints production/pareto/diagnostics
├── clustering.py     ← Orchestrateur (production_clustering, pareto_flotte, diagnostics, legacy)
├── features.py       ← projection UTM 30N (pyproj), matrices haversine/euclidienne
├── algorithms.py     ← kmeans, kmedoids_capacitaire, dbscan_precomputed, affectation_capacitaire (LP)
├── evaluation.py     ← Silhouette, Davies-Bouldin, Calinski-Harabasz, KPI métier (faisabilité, compacité)
├── selection.py      ← pareto(), choisir_k() (garde-fou Silhouette ≥ 0.5)
├── osrm_client.py    ← matrice routière OSRM /table (async, blocs de 50, cache)
├── ms1_client.py     ← capacités flotte MS1 (httpx + Tenacity) — non branché en prod
├── ms2_client.py     ← httpx + Tenacity retry (bulk update)
├── rabbitmq.py       ← Consumer aio-pika + asyncio.Lock() (recalcul auto = production)
├── config.py         ← pydantic-settings
├── data/             ← eleves_meknes.csv (v2), osrm_dist_m.npy (matrice routière cachée)
├── notebooks/        ← clustering_study (CRISP-DM), 02_model_comparison (11 algos), 03_production_strategy
├── requirements.txt
└── .env
```

**requirements.txt (ajouts data-science) :**
```
fastapi==0.111, uvicorn[standard]==0.29, scikit-learn==1.5.2, numpy==2.1
pyproj (UTM), scipy (LP affectation capacitaire), k-means-constrained
httpx==0.27, aio-pika==9.4.1, pydantic-settings==2.3, tenacity==8.2.3
PyJWT==2.8, cryptography==42.0.8
# notebooks : matplotlib, seaborn, folium, jupyter
```

**Endpoints :**
| Route | Auth | Description |
|-------|------|-------------|
| GET `/api/clustering/health` | Public | Health check |
| GET `/api/clustering/eleves` | Public | Tous les élèves (MS2) |
| GET `/api/clustering/sans-groupe` | Public | Élèves sans groupeId |
| GET `/api/clustering/diagnostics` | Public | Stats EDA + `k` recommandé (⌈N/capacité⌉) |
| GET `/api/clustering/quality` | Public | **Garde-fou qualité** : baseline dynamique + seuils + dernier verdict (dashboard admin) ← **NOUVEAU** |
| POST `/api/clustering/production?appliquer=&capacity=&rayon=&road=` | **JWT ADMIN** | **Modèle final** : k-médoïdes capacitaire routier (+ contrainte `rayon` optionnelle) + bulk update MS2 (+ `quality` dans la réponse) |
| POST `/api/clustering/pareto?capacity=&road=` | **JWT ADMIN** | Courbe Pareto qualité vs nb de bus (sans écrire) |
| POST `/api/clustering/kmeans?appliquer=` | **JWT ADMIN** | *(legacy)* K-Means projeté mètres |
| POST `/api/clustering/dbscan?appliquer=` | **JWT ADMIN** | *(legacy)* DBSCAN projeté mètres, bruit → 999 |
| POST `/api/clustering/comparer` | **JWT ADMIN** | *(legacy)* K-Means vs DBSCAN |

**Config de production gelée (`notebooks/production_config.json`, capacité 50) :**
`k=7 bus · Silhouette routier 0.43 · compacité médiane 725 m / max 2409 m · taille_max 50 · faisable ✅ · 17 dispersés`
> Silhouette 0.43 < seuil 0.5 = **arbitrage assumé** capacité ↔ compacité (sans contrainte KMeans monte plus haut mais produit des groupes infaisables).

**Garde-fou qualité DYNAMIQUE (`quality.py`) :** à chaque recalcul, produit un **verdict** `OK / DEGRADE / CRITIQUE`
(informatif, pas un déclencheur). **PAS un seuil fixe 0.5** (qui serait toujours rouge puisque notre silhouette est 0.43) :
- **CRITIQUE** si capacité dépassée (`taille_max > capacité`, contrainte dure) **ou** silhouette < **plancher** (0.75 × 0.4334 ≈ **0.325**, ancré sur le point de conception) ;
- **DEGRADE** si **régression relative** vs référence : silhouette −15 % (et −0.05 abs), ou compacité max +25 %, ou dispersés +15 ;
- **référence dynamique** = `data/quality_baseline.json`, **bootstrap depuis `production_config.json` (0.43, jamais 0.5)**, réécrite à chaque run **OK appliqué** (roulante).
Exposé via `GET /api/clustering/quality` + champ `quality` de `/production` + logs WARNING. Seuils ajustables (`.env` `QUALITY_*`).

**Pattern Bulk Update (anti-DDoS interne) :** une seule requête `PUT /api/eleves/groupes/bulk` au lieu de 300 PATCH.

**Liaison groupe↔bus (B1, `binding.py`) :** à l'**application** du clustering (endpoint `/production?appliquer=true`
et recalcul auto RabbitMQ), MS6 résout chaque groupe (1..k) vers un **bus MS1 actif** (`GET /api/bus/actifs`,
mapping 1-1 par id — capacité uniforme) puis **propage `busId`** aux élèves (`PUT /api/eleves/bus/bulk`).
**Indispensable** : sans ça, `findByBusId` (MS4/ETA) renvoie vide → aucun parent notifié. Dispersés (999) → pas de bus ;
flotte insuffisante / MS1 indispo → dégradé (partiel + WARNING). Rapport `bus_binding` dans la réponse `/production`.

**Consumer RabbitMQ :** queue `ms6.clustering.queue`, keys `eleve.created/gps.updated/deleted` (MS2) + `bus.created/bus.deleted` (MS1, déclencheur « nouveau bus »), `asyncio.Lock()`.
Le recalcul auto utilise désormais `production_clustering` (chemin capacitaire).

**Sécurité JWT :** routes POST protégées par `verify_token` (ADMIN), `jwt_secret` = même valeur que MS7.
**CORS :** aucun (géré uniquement par la Gateway — `CORSMiddleware` retiré).

**Variables .env MS6 :**
```env
MS2_URL=http://localhost:8082
MS1_URL=http://localhost:8081
OSRM_URL=http://localhost:5000
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
JWT_SECRET=<même valeur que MS7 application.properties>
BUS_CAPACITY=50            # capacité uniforme paramétrable
RAYON_MAX_M=0              # distance max élève→médoïde (m) ; 0 = désactivé (ajustable comme la capacité)
USE_ROAD_DISTANCE=true     # distance routière OSRM (false = euclidienne projetée)
EPSG_METRIC=32630          # UTM 30N
MIN_SILHOUETTE=0.50
```

**Démarrage :**
```bash
cd ms6-clustering
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8086 --reload
```

---

### MS8 — API Gateway (port 8080) ✅ mis à jour S7

- JwtAuthFilter → bypass OPTIONS, injecte `X-User-Email`, `X-User-Role`, `X-User-Id`
- Rate limiting Redis : 20 req/s global, 5 req/s sur `/auth`
- CORS global dans `application.yml`
- **Route MS6 à ajouter dans application.yml :**
```yaml
- id: ms6-clustering
  uri: http://localhost:8086
  predicates:
    - Path=/api/clustering/**
  filters:
    - name: RequestRateLimiter
      args:
        redis-rate-limiter.replenishRate: 5
        redis-rate-limiter.burstCapacity: 10
```

---

### MS10 — IncidentService (port 8090) ✅
- `StatutIncident` : `SIGNALE` → `CONFIRME` → `EN_TRAITEMENT` → `RESOLU`
- `TypeIncident` : `ACCIDENT`, `PANNE`, `RETARD`, `ABSENCE_CHAUFFEUR`, `ROUTE_BLOQUEE`, `AUTRE`
- RabbitMQ publie : `incident.signale`, `incident.resolu`
- PATCH `/api/incidents/{id}/statut` → déclenche publication si RESOLU

---

### MS12 — PredictionService ETA (port 8088) ✅ NOUVEAU S8

**Technologie :** Python 3.11 / FastAPI. Prédiction du **temps d'arrivée (ETA)** d'un tronçon de trajet bus.
Démarche data-science identique à MS6 : **benchmark multi-modèles** → choix du meilleur → gel de l'artefact.

**Modèle de production :** choisi par benchmark honnête (**elasticnet** gagnant sur le run actuel).
Le service charge l'artefact gelé de façon **agnostique** (n'importe quel régresseur sklearn/xgboost/lightgbm).

**Stratégie de données (B) — semi-réel ancré OSRM :** durée de base de chaque tronçon = **vraie route OSRM
de Meknès** ; facteurs trafic/météo/Ramadan/souk/travaux issus de la littérature transport ; **incidents**
(panne, accident, route bloquée, absence chauffeur, retard admin) en queue lourde (~5 %/trajet).
`incident_type` = **label** (imprévisible → pas une feature) réutilisable en S12 (anomalies).

**Résultats gelés (`data/eta_config.json`, run OSRM réel) :**
`gagnant elasticnet · R² normaux 0.82 · MAE normaux 0.86 min · gain +52.7 % vs baseline OSRM ·
R² tous 0.16 (incidents irréductibles, assumé)`.

**Fichiers :**
```
ms12-prediction/
├── main.py           ← FastAPI + JWT (ADMIN/CHAUFFEUR) : health / model-info / predict
├── config.py         ← pydantic-settings (port 8088, jwt_secret, osrm_url, chemins artefacts)
├── features.py       ← feature engineering (heure cyclique, one-hot météo/trafic, binaires) — partagé
├── dataset.py        ← générateur ~180 jours d'école, ancré OSRM, facteurs + incidents (seed=42)
├── osrm_client.py    ← durée/distance point-à-point (async service + sync dataset, repli haversine)
├── algorithms.py     ← catalogue des régresseurs candidats (baselines→linéaires→forêts→boosting)
├── train.py          ← split TEMPOREL → benchmark → choix gagnant → gel (model/config/benchmark)
├── model.py          ← chargement/prédiction agnostique du gagnant
├── data/             ← eta_dataset.csv, eta_model.pkl, eta_config.json, benchmark_summary.json
├── notebooks/        ← 01_eta_data_study, 02_model_comparison, 03_production_strategy (+ figures/)
├── requirements.txt  ← Python 3.11 : numpy 1.26.4, pandas, scikit-learn 1.5.2, xgboost 2.1.1, lightgbm 4.5.0
├── Dockerfile        ← EXPOSE 8088
└── .env
```

**Endpoints :**
| Route | Auth | Description |
|-------|------|-------------|
| GET `/api/eta/health` | Public | Health + modèle chargé |
| GET `/api/eta/model-info` | Public | Métriques (tous/normaux), gain vs baseline, importances |
| POST `/api/eta/predict` | **JWT ADMIN/CHAUFFEUR** | ETA d'un trajet (coords→OSRM ou distance/durée fournies) |

**Features (dispo à l'heure de départ) :** temporel (heure sin/cos, jour, mois, moment), conditions
(météo, trafic), route (distance/durée OSRM, nb_feux, traverse_oued), dwell (montées/descentes,
taux_occupation), contexte marocain (ramadan, jour_souk), travaux planifiés, **historique/lag**
(duree_moyenne_historique sans fuite, retard_cumule).

**Protocole d'évaluation :** split **temporel** (30 derniers jours = test), métriques MAE/RMSE/R²/MAPE,
**double vue** (tous trajets vs trajets normaux), baseline métier = durée OSRM brute.

**Pipeline ETA temps réel (G1) — `rabbitmq.py` :** MS12 consomme `gps.bus.updated` (MS3), calcule l'ETA
bus→école (modèle + OSRM), et publie `eta.bus.arriving` dès que l'ETA ≤ `ETA_ALERT_MIN` (10 min) →
MS4 pousse la notif parents (**UC-4**). Réutilise l'endpoint `predict()` (import différé, `auto_context=True`).
Garde-fous : throttle 20 s + cooldown 30 min par bus. `.env` : `RABBITMQ_URL`, `EXCHANGE_NAME`, `ETA_ALERT_MIN`,
`ECOLE_LAT/LNG`. Consumer démarré dans le `lifespan` (mode dégradé si RabbitMQ absent).

**Sécurité JWT :** `verify_token` (même `jwt_secret` que MS7). **CORS :** aucun (géré par la Gateway).

**Démarrage :**
```bash
cd ms12-prediction
pip install -r requirements.txt      # env conda "nlp" (Python 3.11)
python dataset.py                    # génère data/eta_dataset.csv (OSRM requis, sinon repli)
python train.py                      # benchmark + gel du meilleur modèle
uvicorn main:app --host 0.0.0.0 --port 8088
```

> **MS9 ≠ MS12 :** MS9 (port 8089) est réservé au **chatbot LLM** (S9) ; la prédiction ETA est **MS12** (8088).

---

### MS11 — AnalytiqueService / Détection d'anomalies (port 8091) ✅ NOUVEAU (S12 anticipé)

**Technologie :** Python 3.11 / FastAPI. **Détection d'anomalies non supervisée** (Isolation Forest) sur les
trajets de bus, **évaluée** contre le label `incident_type` généré par MS12 (labels = évaluation seulement).
Route Gateway `ms11-analytique` (8091, `/api/analytique/**`) **déjà présente**.

**Données :** **dataset PROPRE à MS11** (`data/anomaly_dataset.csv`, généré par `dataset_anomaly.py`,
indépendant de MS12) avec **anomalies hétérogènes et contextuelles** (~1,25 %) : *franc* (panne/accident,
ratio énorme), *contextuel* (ratio modéré mais conditions légères), *surcharge* (montées anormales).
**Signaux** : `ratio` (franc), **`surprise` = ratio ajusté au contexte** (contextuel), `dwell`/`nb_montees` (surcharge).

**Benchmark de 4 détecteurs (split temporel, budget d'alerte fixe) — résultat gelé :**
| Détecteur | PR-AUC | ROC-AUC | F1 | P | R |
|---|---|---|---|---|---|
| **iforest_curated 🏆** | **0.91** | **1.00** | **0.78** | 0.70 | **0.88** |
| seuil_surprise | 0.80 | 0.99 | 0.63 | 0.55 | 0.75 |
| seuil_ratio | 0.79 | 0.94 | 0.67 | 0.60 | 0.75 |
| iforest_all (dilué) | 0.48 | 0.98 | 0.44 | 0.40 | 0.50 |

> **Triple leçon DS (honnête) :** (1) le **feature engineering** prime (`surprise` contextuelle > ratio brut) ;
> (2) la **curation** prime (`iforest_curated` ≫ `iforest_all` dilué) ; (3) le **multivarié gagne** car les
> anomalies sont hétérogènes (franc+contextuel+surcharge) — aucun seuil univarié ne les capte toutes.
> Contraste avec MS12 (modèle simple gagnant) : ici le problème est **réellement multivarié**. **Scan full : précision 0.70 · rappel 0.72.**

**Fichiers :** `main.py`, `config.py`, `dataset_anomaly.py` (dataset propre), `features.py` (ratio + **surprise**
contextuelle + dwell), `anomaly.py` (seuil | IsolationForest curé, joblib), `train_anomaly.py` (benchmark 4
détecteurs + gel), `osrm_client.py`, `data/` (anomaly_dataset.csv, anomaly_model.pkl, anomaly_config.json,
anomaly_benchmark.json), `notebooks/04_anomaly_detection.ipynb`, Dockerfile, `.env`.

**Endpoints :**
| Route | Auth | Description |
|-------|------|-------------|
| GET `/api/analytique/health` | Public | Health + détecteur chargé |
| GET `/api/analytique/model-info` | Public | Métriques (PR-AUC/ROC/F1), seuil, contamination |
| POST `/api/analytique/anomalies` | **JWT ADMIN** | Un trajet observé (durée réelle + base/coords + contexte) → `{is_anomaly, anomaly_score, ratio, niveau}` |
| GET `/api/analytique/anomalies/scan?limit=` | **JWT ADMIN** | Scanne le dataset → top anomalies + précision/rappel vs incidents réels |
| GET `/api/analytique/live?limit=` | Public | **Monitor GPS live (G3)** : anomalies instantanées détectées en temps réel ← **NOUVEAU** |

**Monitor GPS live (G3, `live_monitor.py` + `rabbitmq.py`) :** MS11 consomme `gps.bus.updated` (queue `ms11.gps.queue`)
et applique des **règles instantanées** (UC-8) : **arrêt prolongé** (immobile > `SEUIL_ARRET_MIN`) et **vitesse anormale**
(> `SEUIL_VITESSE_KMH`). Complément du **détecteur ML** (Isolation Forest, post-hoc au niveau trajet) : le modèle
score des *trajets complets*, inadapté à un ping GPS. Sortie = **buffer mémoire + logs**, exposée par `GET /api/analytique/live`
(pas d'événement sans consommateur ; évolution : `anomalie.detectee` → MS10/MS4 quand un canal admin existera).
La **déviation** (3ᵉ signal UC-8) nécessite la route planifiée persistée (G2).

**Sécurité JWT :** `verify_token` ADMIN (même `jwt_secret` que MS7). **CORS :** aucun (Gateway).
**Démarrage :** `cd ms11-analytique && python train_anomaly.py && uvicorn main:app --port 8091` (env `nlp`).

---

### MS5 — PlanificationService / VRP (port 8085) ✅ NOUVEAU (S10)

**Technologie :** Python 3.11 / FastAPI + **OR-Tools**. **Optimisation des tournées** : le clustering MS6 affecte
les élèves aux bus (capacité) ; MS5 calcule **l'ordre de passage optimal** de chaque bus.

**Modèle :** un **TSP par groupe/bus**, **dépôt = école** (part de l'école → ramasse → revient), coût d'arc =
**durée routière OSRM réelle**. Résolu par **OR-Tools** (`PATH_CHEAPEST_ARC` + `GUIDED_LOCAL_SEARCH`).
Baseline « plus proche voisin » pour mesurer le **gain**. `sens=soir` → dépose sur la **même** tournée
(**même ordre** que le matin, PAS l'inverse) : garder le même ordre équilibre le **temps à bord** sur la journée
(écart-type ≈ 0 vs ~5.8 min si inversé) et, sur OSRM réel (asymétrique), l'inversé non ré-optimisé coûte ~2× plus.
Preuve : `ms5-planification/verify_sens.py`.

**Résultat mesuré (9 bus, données v2) :** distance totale ~108 km · durée ~224 min · **gain moyen ~12.6 %**
vs l'ordre naïf (variable par bus : 0 % si le glouton est déjà optimal).

**Fichiers :** `main.py`, `config.py`, `ms2_client.py` (élèves par groupe, **filtré depuis `/api/eleves`** —
MS5 n'a pas de token utilisateur), `osrm_client.py` (matrice `/table` + géométrie `/route` GeoJSON),
`vrp.py` (OR-Tools TSP + baseline), `planner.py` (orchestrateur), `notebooks/05_vrp_study.ipynb`, Dockerfile, `.env`.

**Endpoints :**
| Route | Auth | Description |
|-------|------|-------------|
| GET `/api/planification/health` | Public | Health + solveur |
| POST `/api/planification/tournee?groupeId=&sens=matin\|soir` | **JWT ADMIN/CHAUFFEUR** | Tournée d'un bus → `{ordre, distance_m, duree_min, gain_vs_baseline_%, geometrie}` |
| POST `/api/planification/tournees?sens=` | **JWT ADMIN/CHAUFFEUR** | Toutes les tournées (lit l'affectation MS6 via MS2) + totaux + gain moyen |

**Sécurité JWT :** `verify_token` ADMIN/CHAUFFEUR (même `jwt_secret` que MS7). **CORS :** aucun (Gateway).
**Gateway :** route `ms5-planification` (8085) **déjà présente** → aucune modif.
**Démarrage :** `cd ms5-planification && uvicorn main:app --port 8085` (env `nlp` + `pip install ortools`).
> **Complémentarité :** MS6 = *quel bus* (affectation capacitaire) ; MS5 = *quel ordre* (temps de tournée).
> Évolution S11 : CVRP global (assignation+routage conjoints) + benchmark vs MS6+TSP.

---

## 🔁 RabbitMQ — Exchange et queues

**Exchange :** `transport.exchange` (TopicExchange, durable)

| Routing Key | Publisher | Consumer | Queue |
|-------------|-----------|----------|-------|
| `eleve.created` | MS2 | MS6 | `ms6.clustering.queue` |
| `eleve.gps.updated` | MS2 | MS6 | `ms6.clustering.queue` |
| `eleve.deleted` | MS2 | MS6 | `ms6.clustering.queue` |
| `bus.created` | **MS1** | MS6 | `ms6.clustering.queue` ← **NOUVEAU (déclencheur « nouveau bus »)** |
| `bus.deleted` | **MS1** | MS6 | `ms6.clustering.queue` ← **NOUVEAU** |
| `gps.bus.updated` | MS3 | MS4 | `ms4.gps.bus.updated.queue` |
| `gps.bus.updated` | MS3 | **MS12** | `ms12.eta.queue` ← **NOUVEAU (pipeline ETA temps réel G1)** |
| `gps.bus.updated` | MS3 | **MS11** | `ms11.gps.queue` ← **NOUVEAU (monitor anomalies GPS live G3)** |
| `eta.bus.arriving` | **MS12** | MS4 | `ms4.eta.arriving.queue` ← **NOUVEAU** |
| `eleve.presence.updated` | **MS2** | MS4 | `ms4.eleve.presence.queue` ← **NOUVEAU (G5 « enfant à bord »)** |
| `incident.signale` | MS10 | MS4 | `ms4.incident.signale.queue` |
| `incident.resolu` | MS10 | MS4 | `ms4.incident.resolu.queue` |

> **Pipeline ETA temps réel (G1) :** `MS3 gps.bus.updated → MS12` calcule l'ETA bus→école (modèle + OSRM),
> et dès que l'ETA ≤ `ETA_ALERT_MIN` (10 min) publie `eta.bus.arriving → MS4` qui pousse la notification
> aux parents (UC-4). Garde-fous : throttle (recalcul ≤ 1×/20 s par bus) + cooldown (alerte ≤ 1×/30 min par bus).
> Limite assumée : alerte à l'arrivée **école** (destination unique) ; l'ETA par arrêt élève nécessite la tournée
> persistée (G2/MS5) + le suivi de présence (G5).

---

## 🔐 Sécurité — Pattern commun MS Java

```java
// 1. JwtUtilsConfig.java
@Bean public JwtUtils jwtUtils() { return new JwtUtils(jwtSecret); }

// 2. JwtAuthFilter.java extends OncePerRequestFilter
// → extrait Bearer → valide → set UserPrincipal dans SecurityContext
// → attribute "jwt_error" si token invalide (distingue 401 manquant vs invalide)

// 3. SecurityConfig.java
@EnableWebSecurity @EnableMethodSecurity
// authenticationEntryPoint → "Token manquant" vs "Token invalide"
// CORS supprimé de chaque MS (géré uniquement Gateway)
```

**RBAC :** `@PreAuthorize("hasRole('ADMIN')")` / `@PreAuthorize("hasAnyRole('ADMIN','CHAUFFEUR')")`

---

## 🧪 Tests & Interfaces HTML

| Fichier | Service(s) | Statut |
|---------|-----------|--------|
| **`html_tests/test-console.html`** | **TOUS** (Auth/Bus/Élèves/GPS/Clustering/Incidents/Notif) — console unifiée + cartes Leaflet (nuages de clusters + bus temps réel) | ✅ **principal** |
| `html_tests/test-gps.html` | MS3 WebSocket GPS | ✅ |
| `html_tests/map-gps.html` | MS3 + OSRM Leaflet | ✅ |
| `html_tests/test-incidents-notifications.html` | MS10 + MS4 | ✅ validé S7 |
| `html_tests/test_ms6.html` | MS6 clustering | ✅ |

**Newman :** 88/88 assertions ✅
**Guide de soutenance :** `docs/DEMO_SOUTENANCE.md` (pipeline DS → démo live → Q/R jury)

---

## 📦 Ordre de démarrage

```bash
# 1. Infrastructure
docker-compose up -d
docker start osrm_meknes

# 2. Java microservices (ordre important)
cd ms7-auth      && mvn spring-boot:run   # 8087
cd ms1-bus       && mvn spring-boot:run   # 8081
cd ms2-eleves    && mvn spring-boot:run   # 8082
cd ms3-localisation && mvn spring-boot:run # 8083
cd ms10-incidents && mvn spring-boot:run  # 8090
cd ms4-notifications && mvn spring-boot:run # 8084
cd ms8-gateway   && mvn spring-boot:run   # 8080 (en dernier)

# 3. Python — MS6 clustering + MS12 prédiction ETA
cd ms6-clustering  && uvicorn main:app --port 8086 --reload
cd ms12-prediction && uvicorn main:app --port 8088 --reload   # env conda "nlp" (Python 3.11)
cd ms11-analytique && uvicorn main:app --port 8091 --reload   # anomalies (env "nlp")
cd ms5-planification && uvicorn main:app --port 8085 --reload  # VRP tournées (env "nlp" + ortools)
# (raccourci : start-all-ms.bat lance tout, chaque MS dans son terminal)
```

---

## 📋 Planning — État d'avancement

| Sprint | Dates | Statut | Contenu |
|--------|-------|--------|---------|
| S1 | 13-19/05 | ✅ | Conception, UML, GitHub |
| S2 | 20-26/05 | ✅ | Docker Compose base |
| S3 | 27/05-02/06 | ✅ | PostgreSQL+Redis+RabbitMQ, MS7-Auth |
| S4 | 03-09/06 | ✅ | MS1-Bus, MS2-Eleves, MS8-Gateway, Newman 88/88 |
| S5 | 10-16/06 | ✅ | MS3-Localisation, WebSocket GPS, Seeding 300 élèves |
| S6 | 17-23/06 | ✅ | OSRM, Simulateur bus, MS10-Incidents, MS4-Notifications FCM |
| **S7** | **24-30/06** | **✅** | **MS6 Clustering refonte expert v3 (UTM, k-médoïdes capacitaire routier OSRM, Pareto, 3 notebooks CRISP-DM), données v2, console de test unifiée + cartes, fix CORS** |
| **S8** | **01-07/07** | **🔄** | **Prédiction ETA ✅ (MS12 : dataset 180j ancré OSRM, benchmark multi-modèles → elasticnet, 3 notebooks CRISP-DM, service :8088). Reste : 5 déclencheurs clustering évolutifs** |
| S9 | 08-14/07 | ⏳ | Chatbot LLM Mistral/Groq LangChain, FastAPI endpoints ETA |
| S10 | 15-21/07 | 🔄 | **VRP OR-Tools ✅ anticipé (MS5 : TSP par bus, dépôt=école, distances OSRM, gain moyen ~12.6 %, notebook 05, service :8085). Reste : Flutter parent v1, context injection LLM** |
| S11 | 22-28/07 | ⏳ | Dashboard admin, Flutter notifications, VRP benchmark |
| S12 | 29/07-04/08 | 🔄 | **Détection d'anomalies ✅ anticipée (MS11 : dataset propre anomalies contextuelles, Isolation Forest curé gagnant PR-AUC 0.91/rappel 0.88, notebook 04, service :8091). Reste : KPIs dashboard, Flutter chatbot** |
| S13 | 05-11/08 | ⏳ | Tests e2e, Déploiement, Documentation |
| S14-S15 | 12-25/08 | ⏳ | Mémoire, Slides, Vidéo démo, Soutenance |

---

## 🔜 Prochaine étape : S8

1. **Dataset ETA 180 jours** — générer données synthétiques réalistes (heure, météo, trafic, retard)
2. **XGBoost ETA** — entraîner modèle de prédiction temps d'arrivée, exposer via FastAPI (MS9 ou extension MS6)
3. **5 déclencheurs clustering évolutifs** — recalcul automatique basé sur : ajout élève, déménagement, nouveau bus, seuil Silhouette dégradé, planification admin

---

## ⚠️ Points d'attention pour S8

1. **MS6 JWT_SECRET** : doit être identique à `app.jwt.secret` dans MS7 `application.properties` — à configurer dans `ms6-clustering/.env`

2. **Firebase en mode dégradé** : ECHEC en DB est normal. Pour activer FCM réel → télécharger `firebase-service-account.json` depuis Firebase Console → placer dans `ms4-notifications/src/main/resources/` → ajouter à `.gitignore`

3. **MS8 dépréciations** : `spring.cloud.gateway.routes` → `spring.cloud.gateway.server.webflux.routes` (non bloquant)

4. **MS6 route Gateway** : ajouter la route MS6 dans `application.yml` MS8 (fichier `ms8-gateway-route.yml` fourni)

5. **Python 3.13** : utiliser `scikit-learn==1.5.2`, `numpy==2.1.0`, `cryptography==42.0.8` (pas les versions antérieures)

---

## 💡 Décisions architecturales clés

| Décision | Raison |
|----------|--------|
| JwtUtils = Java pur (pas @Component) | ms-common sans dépendance Spring |
| Double validation JWT (Gateway + MS) | Defense in depth |
| MS4→MS2 direct (pas via Gateway) | MS4 n'a pas de token utilisateur |
| Pas de @ManyToOne cross-service | Indépendance totale des bases de données |
| Bulk update au lieu de N PATCH | Anti-DDoS interne, 1 transaction PostgreSQL |
| **Projection UTM 30N (≠ StandardScaler)** | **Distance vraie en mètres à 33.9°N ; Silhouette interprétable** |
| **Distance routière OSRM (k-médoïdes)** | **La distance à vol d'oiseau sous-estime de 1.5–1.7× le trajet réel** |
| **Affectation capacitaire globale (LP)** | **Garantit taille de groupe ≤ capacité bus par construction** |
| **Capacité = paramètre uniforme** | **Tous les bus même taille, modifiable ; k = ⌈N/capacité⌉ dérivé (jamais fixé)** |
| **Choix du nb de bus par Pareto** | **Aide à la décision qualité vs flotte (pas un chiffre arbitraire)** |
| asyncio.Lock() sur recalcul | Évite burst de recalculs simultanés RabbitMQ |
| Tenacity retry (3 essais expo) | Résilience si MS2 redémarre pendant clustering |
| groupeId=999 pour bruit DBSCAN | Sentinel (legacy) ; en production les dispersés sont affectés au médoïde le plus proche |
| **CORS uniquement sur la Gateway** | **Retiré de MS1/MS2/MS3/MS6 (en-têtes en double = "Failed to fetch")** |
| Routes internes MS6→MS2 permitAll | MS6 Python ne gère pas de token Spring JWT |
