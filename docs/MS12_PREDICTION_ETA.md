# 📘 MS12 — Service de prédiction ETA (temps d'arrivée)
### Documentation détaillée — choix des features, calcul, utilisation et modèles testés
*Transport Scolaire Intelligent — PFE SDIA · Meknès · Sprint S8*

---

## 1. À quoi sert MS12 ?

MS12 prédit la **durée réelle (en minutes) d'un tronçon de trajet** d'un bus scolaire, c'est-à-dire le
temps qu'il mettra pour aller d'un point A à un point B **compte tenu du contexte** (heure, trafic, météo,
nombre d'arrêts, etc.). En chaînant les tronçons, on obtient l'**heure d'arrivée estimée (ETA)** à l'école
ou à un arrêt — information utile aux parents et à l'administration.

> **Pourquoi un modèle et pas juste OSRM ?** OSRM donne une durée « théorique » (réseau routier, vitesse
> libre). En réalité, le trafic aux heures de pointe, la pluie, le nombre d'élèves qui montent, etc.
> allongent le trajet. Le modèle **apprend ces écarts** et corrige la durée OSRM.
> Résultat mesuré : **−52.7 % d'erreur** par rapport à la durée OSRM brute (voir §6).

---

## 2. Vue d'ensemble : comment tout s'articule

```
        dataset.py ──► eta_dataset.csv         (données d'entraînement, ancrées OSRM réel)
             │
             ▼
        features.py  (transforme le brut en matrice numérique — MÊME code partout)
             │
             ▼
        train.py ──► benchmark de 10 modèles ──► choisit le meilleur ──► GÈLE :
             │                                          • data/eta_model.pkl         (le modèle)
             │                                          • data/eta_config.json       (métriques + ordre des features)
             │                                          • data/benchmark_summary.json(comparatif complet)
             ▼
        main.py (FastAPI :8088)  ── au démarrage, CHARGE eta_model.pkl
             │
             ▼
        POST /api/eta/predict  ──►  requête ──► OSRM (durée de base) ──► features.py ──► modèle ──► ETA
```

**Point clé de cohérence :** les notebooks, `train.py` et le service **appellent tous `features.py`**.
Le modèle « constaté » dans le notebook 02 est donc **exactement** celui servi par l'API — aucune divergence
possible entre l'analyse et la production.

---

## 3. Les données : comment le dataset est construit

Fichier : `ms12-prediction/dataset.py` → produit `data/eta_dataset.csv` (**4320 lignes = 180 jours d'école
× 2 services × 3 circuits × ~4 tronçons**).

### 3.1 Stratégie « semi-réelle » ancrée sur OSRM
On ne fabrique pas des distances au hasard. La **base** de chaque tronçon (distance en mètres, durée de
référence en secondes) provient des **vraies routes OSRM du réseau de Meknès** (`osrm_client.route_sync`).
Si OSRM est éteint, repli à vol d'oiseau × 1.4 (~30 km/h). Les arrêts réutilisent les circuits réels de
`html_tests/map-gps.html` et l'école Al Massira `(33.893, -5.5455)`.

### 3.2 Périmètre calendaire
On génère **uniquement les jours d'école** : week-ends, vacances scolaires et jours fériés marocains sont
**exclus** (pas de service ce jour-là → ce ne sont donc pas des features). Le **Ramadan** garde un service
(horaires ajustés) et devient une variable de contexte.

### 3.3 Comment la durée réelle (cible) est calculée
Pour chaque tronçon, la durée réelle simulée est :

```
duree_reelle = duree_base_OSRM × f_trafic × f_meteo × f_ramadan × f_souk × f_travaux
             + dwell (temps d'embarquement)
             + bruit_irréductible
             (+ retard d'incident, rare)
```

Les **facteurs multiplicatifs** viennent de la littérature transport (ordres de grandeur documentés) :

| Facteur | Valeurs |
|---|---|
| `f_trafic` | fluide ×1.00 · modéré ×1.15 · dense ×1.40 · embouteillage ×1.80 |
| `f_meteo` | ensoleillé ×1.00 · nuageux ×1.03 · pluie ×1.20 · brouillard ×1.15 |
| `f_ramadan` | ×1.25 le soir (avant l'iftar), ×1.05 le matin |
| `f_souk` | ×1.12 le jour de souk (mercredi) |
| `f_travaux` | ×1.30 si travaux planifiés |
| `dwell` | (montées + descentes) × 4 s |
| `bruit` | gaussien, écart-type = 10 % de la durée (part **irréductible** = aléa réel) |

### 3.4 Les cas extrêmes (incidents) — un choix assumé
~5 % des trajets subissent un **incident imprévisible** (`panne` +20-60 min, `accident` +30-90 min,
`route_bloquee` +10-40 min, `absence_chauffeur` +30-120 min, `retard_admin` +5-20 min).

> **Décision data-science importante :** l'`incident_type` **n'est PAS une feature** du modèle, car il est
> **imprévisible à l'heure de départ** (on ne sait pas qu'une panne va survenir). Il est conservé comme
> **label** → il servira à la **détection d'anomalies du sprint S12 (Isolation Forest)**. Conséquence : ces
> trajets sont des *outliers non prédictibles* qui **plafonnent honnêtement le R²** (voir §6).

---

## 4. Les features : choix, justification et calcul

Fichier : `ms12-prediction/features.py`. **Principe de sélection :** on ne garde que des variables
**disponibles à l'heure de départ** (sinon ce serait de la triche : on ne peut pas prédire avec une
information qu'on n'a pas encore). Chaque feature ajoutée correspond à une **cause réelle** du temps de trajet.

### 4.1 Catalogue complet (26 colonnes après transformation)

| Feature (modèle) | Origine / calcul | Pourquoi (validité) |
|---|---|---|
| `heure_sin`, `heure_cos` | `heure_depart` → `sin/cos(2π·h/24)` | Heure **cyclique** : 23 h proche de 0 h. Capte les pointes. |
| `is_soir` | `moment == "soir"` → 0/1 | Sens du trajet (vers école / retour). |
| `jour_semaine`, `mois` | date | Effets hebdo/saisonniers. |
| `distance_routiere_m` | **OSRM** (réel) | Plus c'est loin, plus c'est long. |
| `duree_base_s` | **OSRM** (réel) | Durée théorique = socle de la prédiction (feature #1). |
| `duree_moyenne_historique_s` | moyenne des durées réalisées **des jours passés** (même circuit/moment/tronçon) | « Ce tronçon prend d'habitude X min » — top prédicteur en ETA. **Sans fuite** (voir 4.3). |
| `retard_cumule_s` | somme des retards des tronçons déjà parcourus ce jour | Un bus déjà en retard tend à le rester. |
| `nb_arrets_restants` | position dans le circuit | Plus d'arrêts à venir = plus d'aléa. |
| `nb_montees`, `nb_descentes` | simulés par arrêt | Temps d'arrêt (**dwell**) = vraie composante du trajet bus. |
| `taux_occupation` | occupants / capacité (50) | Corrélé aux montées/descentes. |
| `nb_feux` | constante par circuit | Les feux ralentissent (proxy structurel). |
| `traverse_oued` | constante par circuit (0/1) | Goulot d'étranglement (cohérent avec les données v2). |
| `ramadan`, `jour_souk`, `travaux_prevus` | calendrier / planning | Contexte marocain + événement **connu à l'avance**. |
| `meteo_*` (4 colonnes one-hot) | catégorie météo | Pluie/brouillard ralentissent. |
| `trafic_*` (4 colonnes one-hot) | catégorie trafic | Effet le plus fort après la distance. |

### 4.2 Comment les catégories deviennent numériques
- **Heure → cyclique** (`sin`/`cos`) pour la continuité 23 h↔0 h.
- **Météo / trafic → one-hot** (une colonne 0/1 par catégorie) : traitement **équitable** pour les modèles
  linéaires (pas de faux ordre numérique).
- **Binaires** (ramadan, souk, travaux, oued, is_soir) : 0/1.
- **Numériques** (distances, durées, comptes) : passées telles quelles.
- L'**ordre des colonnes est figé** dans `eta_config.json` → à la prédiction, `model.py` réaligne les
  colonnes (`reindex`), garantissant que le modèle reçoit toujours les features dans le même ordre.

### 4.3 Le piège évité : la fuite de données (data leakage)
La feature `duree_moyenne_historique_s` pourrait facilement « tricher ». On la calcule donc **uniquement
sur les jours passés** (moyenne glissante décalée d'un cran, `expanding().mean().shift(1)`), jamais sur le
jour courant. C'est **la** raison pour laquelle nos scores sont crédibles et non gonflés.

### 4.4 Variables volontairement écartées (étude de faisabilité/validité)
- `chauffeur_id` : risque de fuite / sur-apprentissage.
- Météo continue détaillée (température, vent) : sur-ingénierie, la catégorie suffit.
- `vacances_scolaires` / `jours fériés` : reclassés en **restriction calendaire** (pas de trajet), pas en feature.

---

## 5. Comment on utilise le modèle (production)

Fichiers : `main.py` (API) + `model.py` (chargement agnostique).

### 5.1 Endpoints
| Route | Auth | Rôle |
|---|---|---|
| `GET /api/eta/health` | public | service up + modèle chargé |
| `GET /api/eta/model-info` | public | métriques, gain vs baseline, importances des features |
| `POST /api/eta/predict` | **JWT ADMIN/CHAUFFEUR** | prédit l'ETA d'un trajet |

### 5.2 Déroulé d'une prédiction
1. La requête donne soit les **coordonnées** (bus + destination), soit directement `distance_routiere_m` +
   `duree_base_s`.
2. Si coordonnées → le service interroge **OSRM** pour la durée/distance de base.
3. On construit une ligne brute (heure, trafic, météo, arrêts…), passée à `features.preparer_features`.
4. `model.py` réaligne les colonnes et appelle le modèle gelé → **ETA en minutes**.
5. Réponse : `eta_minutes`, `intervalle_min` (± MAE), `heure_arrivee_estimee`, `facteurs`, `modele`.

### 5.3 Exemple réel (validé)
| Scénario | ETA prédite |
|---|---|
| Médina → École, **fluide + ensoleillé** | **3.84 min** (durée OSRM base 3.58) |
| Même trajet, **embouteillage + pluie + 8 montées** | **8.42 min** |

→ Le modèle réagit correctement : trafic dense + pluie + embarquements ⇒ ETA nettement plus longue.

### 5.4 Accès via la Gateway
Route ajoutée dans MS8 : `Path=/api/eta/**` → `http://localhost:8088`, filtrée par `JwtAuthFilter`.
Le token JWT est le même que MS7 (secret partagé).

---

## 6. Les modèles testés (benchmark) et le choix du gagnant

Fichiers : `algorithms.py` (catalogue) + `train.py` (benchmark).

### 6.1 Protocole d'évaluation honnête
- **Split temporel** : les 30 derniers jours d'école = **test** (jamais vus à l'entraînement) → mesure la
  vraie capacité de généralisation, pas la mémorisation.
- **Métriques** : MAE (minutes, l'erreur moyenne), RMSE, R² (variance expliquée), MAPE (%).
- **Double vue** : *tous les trajets* (avec incidents) **et** *trajets normaux* (sans incident).
- **Baselines de référence** : la moyenne, et surtout la **durée OSRM brute** (ce qu'on ferait sans ML).

### 6.2 Résultats complets (run avec OSRM réel)

| Modèle | MAE tous (min) | R² tous | **MAE normaux** | **R² normaux** | fit (s) |
|---|---|---|---|---|---|
| **elasticnet 🏆** | **1.322** | 0.164 | **0.859** | **0.820** | 0.006 |
| ridge | 1.367 | 0.155 | 0.901 | 0.806 | 0.005 |
| linear | 1.367 | 0.154 | 0.902 | 0.806 | 0.009 |
| knn | 1.452 | 0.163 | 0.997 | 0.622 | 0.003 |
| gradient_boosting | 1.476 | 0.099 | 1.014 | 0.446 | 1.03 |
| extra_trees | 1.549 | −0.131 | 1.086 | −0.922 | 1.47 |
| random_forest | 1.567 | −0.011 | 1.102 | −0.151 | 2.38 |
| xgboost | 1.675 | −0.044 | 1.212 | −0.361 | 0.54 |
| hist_gb | 1.705 | 0.085 | 1.245 | 0.425 | 0.26 |
| lightgbm | 1.926 | 0.026 | 1.467 | 0.085 | 0.29 |
| *baseline_moyenne* | 2.709 | −0.005 | 2.266 | −0.125 | — |
| *baseline_osrm* | 2.796 | −0.077 | 2.324 | −0.252 | — |

**Gagnant : `elasticnet`** (régression linéaire régularisée L1+L2) — meilleur MAE.
Gain **+52.7 %** vs la durée OSRM brute (2.796 → 1.322 min).

### 6.3 Deux enseignements à défendre devant le jury

**(a) Pourquoi le R² « tous trajets » est bas (0.16) — et c'est normal.**
Les incidents (jusqu'à ~100 min sur un trajet de 3-6 min) sont **imprévisibles** et gonflent la variance.
Le R² qui compte est celui des **trajets normaux : 0.82** (MAE **0.86 min**), dans la cible visée (0.75-0.85).
Message : *le modèle est excellent sur le prévisible, honnête sur l'imprévisible*.

**(b) Pourquoi un modèle linéaire bat XGBoost/LightGBM ici.**
La relation simulée est essentiellement **multiplicative de facteurs** que le one-hot + linéaire capture
très bien. Les modèles à arbres **sur-apprennent** le bruit et les outliers du train, puis généralisent
moins bien sur le test temporel (décalage saisonnier). C'est un **résultat pédagogique fort** : *le meilleur
modèle n'est pas le plus complexe, mais celui qui généralise le mieux sur des données honnêtement séparées*.

### 6.4 Interprétabilité (importance des features)
Top facteurs du modèle retenu (coefficients absolus, features standardisées) :
`duree_base_s` ≫ `trafic_embouteillage` > `travaux_prevus` > `trafic_fluide` > `meteo_pluie` >
`distance_routiere_m` > `duree_moyenne_historique_s` > `ramadan`…
→ cohérent avec le bon sens métier : la durée de base et le trafic dominent. (Figure SHAP dans le notebook 03.)

---

## 7. Reproduire de A à Z

```bash
conda activate nlp            # Python 3.11
cd ms12-prediction
pip install -r requirements.txt
docker start osrm_meknes      # OSRM Meknès sur :5000 (sinon repli vol d'oiseau)

python dataset.py             # -> data/eta_dataset.csv
python train.py               # -> benchmark + eta_model.pkl + eta_config.json + benchmark_summary.json
uvicorn main:app --port 8088  # service ; tester via html_tests/test-console.html (onglet ETA)

# notebooks (démarche complète, avec figures) :
python notebooks/build_notebooks.py
jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb
```

---

## 8. Notebooks (démarche CRISP-DM, pour le mémoire)

| Notebook | Contenu |
|---|---|
| `01_eta_data_study.ipynb` | Compréhension métier, EDA, distribution à queue lourde, corrélations, effets contextuels, feature engineering |
| `02_model_comparison.ipynb` | Benchmark des 10 modèles, barres MAE, R² normal vs tous, **on constate le gagnant** |
| `03_production_strategy.ipynb` | Prédit vs réel, résidus, importances, **SHAP**, **gel** du modèle de production |

Figures exportées dans `notebooks/figures/` (10 PNG).

---

## 9. Limites et perspectives (honnêteté scientifique)

- **Données synthétiques** (ancrées OSRM mais pas terrain) : la validité prédictive réelle nécessiterait
  une **collecte GPS réelle** (perspective). Le livrable prouve la **méthodologie** et le **pipeline**.
- **Incidents non prédits volontairement** → alimentent la **détection d'anomalies S12**.
- **Flotte / circuits** limités à 3 exemples (extensible).
- Prochaine évolution : brancher la **position GPS temps réel (MS3)** pour un ETA « live ».

---

### 📂 Fichiers de référence
- Code : `ms12-prediction/*.py`
- Artefacts gelés : `ms12-prediction/data/{eta_model.pkl, eta_config.json, benchmark_summary.json}`
- Notebooks : `ms12-prediction/notebooks/`
- Résumé projet : `CLAUDE.md` (section MS12) · Démo : `docs/DEMO_SOUTENANCE.md`
