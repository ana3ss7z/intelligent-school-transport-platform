# 📗 MS11 — Service de détection d'anomalies
### Documentation détaillée — données, fonctionnement du ML, benchmark et utilisation
*Transport Scolaire Intelligent — PFE SDIA · Meknès · Sprint S12 (anticipé)*

---

## 1. À quoi sert MS11 ?

MS11 **repère automatiquement les trajets de bus « anormaux »** — ceux qui ont pris **beaucoup plus de
temps que prévu** à cause d'un **incident** (panne, accident, route bloquée, absence du chauffeur, retard
administratif). Objectif : **alerter l'administration** quand un trajet sort de l'ordinaire.

> **Lien avec MS12 (prédiction ETA).** MS12 prédit la durée **normale** d'un trajet mais **ne peut pas
> prédire** un incident (imprévisible à l'heure de départ). MS11 fait le complément : sur des trajets
> **déjà effectués**, il **détecte** ceux qui étaient anormaux. Les deux services **partagent le même
> jeu de données** et le label `incident_type` — la boucle est bouclée.

---

## 2. La notion d'« anomalie » et le choix du modèle

### 2.1 Apprentissage **non supervisé** — pourquoi ?
On pourrait entraîner un classifieur supervisé « incident / pas incident ». Mais en vrai :
- les incidents sont **rares** (~1 % des trajets) → jeu très déséquilibré,
- on veut détecter **l'inhabituel en général**, y compris des cas **jamais vus**.

→ On utilise donc la **détection d'anomalies non supervisée** : le modèle apprend à quoi ressemble un
trajet **normal**, et signale tout ce qui s'en écarte. **Le label `incident_type` n'est JAMAIS utilisé
pour entraîner** — seulement pour **évaluer** (vérité terrain). C'est la démarche honnête standard.

### 2.2 Isolation Forest — comment ça marche (simplement)
**Isolation Forest** est l'algorithme de référence pour la détection d'anomalies. Idée intuitive :
- Il construit des arbres en **coupant l'espace au hasard**.
- Un point **anormal** (isolé, loin des autres) est **séparé en très peu de coupes** ; un point normal
  (au milieu de la foule) demande **beaucoup de coupes**.
- Le **score d'anomalie** = à quel point le point est facile à isoler. Plus c'est facile → plus c'est anormal.

> Analogie : dans une salle bondée, retrouver quelqu'un d'unique (très grand, habillé en rouge) prend
> **peu de questions** ; retrouver une personne « moyenne » en prend beaucoup. Isolation Forest mesure
> exactement ce « peu de questions ».

Avantages : rapide, non supervisé, pas besoin de définir « à la main » ce qu'est une anomalie.

---

## 3. Les données

**Source :** le fichier **`eta_dataset.csv` produit par MS12** (aucune donnée n'est régénérée ici).
Chaque ligne = un **tronçon de trajet** un jour donné, avec :
- `duree_reelle_min` : la durée **réellement observée** (cible de MS12),
- `duree_base_s` : la durée **théorique OSRM** (réseau réel de Meknès),
- le **contexte** (météo, trafic, arrêts, occupation, ramadan…),
- `incident_type` ∈ {none, panne, accident, route_bloquee, absence_chauffeur, retard_admin} = **label**.

**Chiffres :** 4320 trajets, dont **~1,2 % d'incidents** (queue lourde : un incident ajoute +20 à +120 min
à un trajet normalement de 3–6 min).

### Le signal clé : le **ratio**
```
ratio = durée réelle / durée de base OSRM
```
- Trajet **normal** : ratio ≈ 1,0 à 1,8 (un peu plus long à cause du trafic/météo).
- Trajet **avec incident** : ratio **explose** (5×, 10×, 40×…).

Ce ratio est **auto-suffisant** : il capte l'anomalie **sans dépendre du modèle ETA de MS12** → MS11 reste
un service autonome. (Médiane observée : ratio normal ≈ 1,1 · ratio incident ≈ très élevé.)

---

## 4. Feature engineering (`features.py`)

On transforme chaque trajet observé en variables numériques. `incident_type` est **exclu** (c'est le label).

| Feature | Rôle |
|---|---|
| **`ratio`** = durée réelle / durée base | **signal principal** d'anomalie |
| `ecart_min` = réel − base (minutes) | écart absolu |
| `retard_cumule_s` | retard accumulé sur le circuit |
| `duree_base_s`, `distance_routiere_m` | contexte route |
| `dwell` = montées + descentes, `taux_occupation` | activité aux arrêts |
| `nb_arrets_restants`, `nb_feux`, `traverse_oued` | structure du circuit |
| `ramadan`, `jour_souk`, `travaux_prevus`, `is_soir` | contexte |
| one-hot `meteo_*`, `trafic_*` | conditions |

Deux « vues » sont testées :
- **avec résultat** (`with_outcome=True`) : inclut ratio/écart/retard → le détecteur « voit » le résultat.
- **sans résultat** (`with_outcome=False`) : contexte de départ seulement → détecteur « aveugle » (témoin).

---

## 5. Benchmark honnête des détecteurs (`train_anomaly.py`)

### 5.1 Protocole
- **Split temporel** : 30 derniers jours = test (jamais vus à l'entraînement).
- **Entraînement non supervisé** (sans labels) ; labels utilisés **seulement pour évaluer**.
- **Budget d'alerte fixe** : on signale les *contamination %* trajets les plus anormaux → comparaison
  **équitable** entre détecteurs (évite le biais de calibration de seuil).
- **Métriques** : PR-AUC (adaptée au déséquilibre), ROC-AUC, F1, précision, rappel, matrice de confusion.

### 5.2 Résultats (gelés dans `data/anomaly_benchmark.json`)

| Détecteur | PR-AUC | ROC-AUC | F1 | Précision | Rappel | Confusion (test) |
|---|---|---|---|---|---|---|
| `iforest_contexte` (aveugle) | 0.008 | 0.36 | 0.00 | 0.00 | 0.00 | 7 incidents ratés |
| `iforest_ratio` | 0.37 | **0.98** | 0.35 | 0.30 | 0.43 | 3/7 détectés |
| **`seuil_ratio` 🏆** | **1.00** | **1.00** | **0.82** | 0.70 | **1.00** | **7/7 détectés, 3 faux positifs** |

> Matrice de confusion du gagnant (test) : `[[710 TN, 3 FP], [0 FN, 7 TP]]` → **aucun incident manqué**.

### 5.3 Interprétation (honnête — à défendre)
- **Le détecteur « aveugle » échoue** (PR-AUC 0.008) : logique, on **ne peut pas** deviner un incident à
  partir du seul contexte de départ. C'est cohérent avec MS12 (les incidents sont imprévisibles a priori).
- **Le signal est unidimensionnel** : le `ratio` sépare quasi parfaitement incidents et trajets normaux.
  Un **simple seuil** attrape donc **100 % des incidents** (rappel 1.0) avec 70 % de précision.
- **Isolation Forest confirme** (ROC-AUC 0.98) mais **n'apporte pas de gain multivarié ici** : le problème
  est de faible dimension. C'est un **résultat de parcimonie** — exactement le même enseignement que MS12
  (où elasticnet battait XGBoost) : **on ne suppose pas que le modèle complexe gagne, on le prouve**.
- **Isolation Forest reste pertinent** comme détecteur **général** : pour des anomalies plus subtiles ou
  multivariées (données réelles bruitées), il détecte des écarts qu'un seuil unique manquerait.

### 5.4 Le modèle gelé
`detecteur = seuil_ratio` · `seuil = 3.53` (ratio) · `contamination = 0.013`.
Un trajet est une **anomalie si son ratio ≥ 3.53** (durée réelle ≥ 3,5× la durée théorique).
Artefacts : `anomaly_model.pkl` (objet détecteur), `anomaly_config.json` (seuil, métriques), `anomaly_benchmark.json`.

---

## 6. Comment on l'utilise (service `main.py`)

Sécurité : **JWT ADMIN** (même secret que MS7). CORS : géré uniquement par la Gateway. Route déjà câblée :
`/api/analytique/**` → port 8091.

| Route | Auth | Rôle |
|---|---|---|
| `GET /api/analytique/health` | public | service up + détecteur chargé |
| `GET /api/analytique/model-info` | public | métriques (PR-AUC/ROC/F1), seuil, contamination |
| `POST /api/analytique/anomalies` | **JWT ADMIN** | un trajet observé → anomalie ? |
| `GET /api/analytique/anomalies/scan?limit=` | **JWT ADMIN** | scanne le dataset → top anomalies + précision/rappel |

### Déroulé d'une détection (`POST /anomalies`)
1. Entrée : `duree_reelle_min` (observée) + `duree_base_s` (ou coordonnées → OSRM) + contexte.
2. Le service calcule les features (dont le `ratio`).
3. Le détecteur renvoie un **score d'anomalie** ; `is_anomaly = score ≥ seuil`.
4. Réponse : `{ is_anomaly, anomaly_score, seuil, ratio_reel_base, niveau }` (niveau : normal / suspect / critique).

**Exemples réels (validés) :**
| Trajet | Ratio | Résultat |
|---|---|---|
| Normal (3,8 min / base 3,6 min) | 1,06 | `is_anomaly: false` · normal |
| Panne (42 min / base 3,6 min) | 11,7 | `is_anomaly: true` · **critique** |

### Scan global (`GET /anomalies/scan`)
Passe tout le dataset au détecteur et renvoie les **top anomalies** + un bilan vs incidents réels.
**Résultat mesuré sur l'ensemble : précision 0,88 · rappel 0,93** (56 détectées / 53 incidents réels ;
les top anomalies sont bien des `absence_chauffeur` / `accident`). Idéal pour un futur **dashboard KPI**.

---

## 7. Reproduire de A à Z

```bash
conda activate nlp                 # Python 3.11
cd ms11-analytique
pip install -r requirements.txt
# (le dataset vient de MS12 : ../ms12-prediction/data/eta_dataset.csv)

python train_anomaly.py            # benchmark + gel : anomaly_model.pkl / anomaly_config.json / anomaly_benchmark.json
uvicorn main:app --port 8091       # service ; tester via la Gateway ou en direct

# notebook (démarche complète, figures) :
python notebooks/build_notebooks.py
jupyter nbconvert --to notebook --execute --inplace notebooks/04_anomaly_detection.ipynb
```

---

## 8. Notebook (démarche CRISP-DM)

`notebooks/04_anomaly_detection.ipynb` — markdown explicatif avant chaque cellule :
compréhension métier → EDA du `ratio` (séparation normal/incident) → feature engineering → **benchmark**
des 3 détecteurs → **courbes ROC & Précision-Rappel** → matrice de confusion → interprétation → **gel**.
Figures dans `notebooks/figures/` (distribution ratio, ROC/PR, confusion).

---

## 9. Architecture & fichiers

```
ms11-analytique/                     (port 8091, /api/analytique/**)
├── main.py            ← FastAPI + JWT : health / model-info / anomalies / anomalies/scan
├── config.py          ← port, jwt_secret, chemin dataset ETA, contamination
├── features.py        ← features d'anomalie (ratio + contexte) ; incident_type EXCLU
├── anomaly.py         ← détecteur unifié (IsolationForest | seuil-ratio), persistance joblib
├── train_anomaly.py   ← benchmark + évaluation vs incident_type + gel du gagnant
├── osrm_client.py     ← durée/distance de base (option coords)
├── data/              ← anomaly_model.pkl, anomaly_config.json, anomaly_benchmark.json
├── notebooks/         ← 04_anomaly_detection.ipynb + figures/
├── requirements.txt · Dockerfile · .env
```
**Réutilise** : le pattern service de MS12 (config pydantic, `verify_token` JWT, chargement joblib agnostique,
Dockerfile, générateur de notebooks). **Gateway** : route `ms11-analytique` déjà présente → aucune modif.

---

## 10. Limites & perspectives (honnêteté scientifique)

- **Données synthétiques** (ancrées OSRM) : la validité réelle demanderait des trajets GPS terrain
  (perspective). Le livrable prouve la **méthodologie** et le **pipeline**.
- **Anomalie unidimensionnelle** : sur ces données, le `ratio` suffit ; Isolation Forest apporterait plus
  sur des anomalies **subtiles/multivariées** (réelles).
- **Détection a posteriori** : on détecte après le trajet. Évolution : détection **en temps réel** au fil
  du GPS (MS3), et **dashboard KPI** (S12) branché sur `/anomalies/scan`.

---

### 📂 Références
- Code : `ms11-analytique/*.py` · Artefacts : `ms11-analytique/data/anomaly_*.{pkl,json}`
- Notebook : `ms11-analytique/notebooks/04_anomaly_detection.ipynb`
- Données : `ms12-prediction/data/eta_dataset.csv` · Doc ETA : `docs/MS12_PREDICTION_ETA.md`
- Résumé projet : `CLAUDE.md` (section MS11)
