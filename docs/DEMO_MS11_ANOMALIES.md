# 🎓 Guide de soutenance — MS11 Détection d'anomalies
### Ce qu'il faut dire au professeur (Pr. Ali Bekri)

> **Fil directeur : honnêteté scientifique.** MS11 n'est pas « magique ». On raconte *pourquoi* on détecte,
> *ce que le ML apporte réellement* (et ce qu'il n'apporte pas), et *où est la vraie valeur métier*.
> C'est cette lucidité qui impressionne un jury data-science, pas un score parfait.

---

## ⏱️ Plan de la démo (≈ 7 min)

| Bloc | Durée | Objectif |
|------|-------|----------|
| 0. Contexte | 1 min | Pourquoi détecter des anomalies ? Lien avec MS12 |
| 1. **Pipeline Data Science** | 3 min | Feature engineering + benchmark honnête |
| 2. **Démonstration live** | 2 min | 3 cas : panne / normal justifié / surcharge |
| 3. Questions du jury | 1 min | Assumer les limites (a posteriori, ML vs seuil) |

---

## 0️⃣ Contexte — la phrase d'accroche (1 min)

> « MS12 prédit la durée **normale** d'un trajet, mais **ne peut pas prédire** un incident (panne, accident) —
> c'est imprévisible à l'heure de départ. MS11 fait le **complément** : sur des trajets **déjà effectués**, il
> **détecte** ceux qui étaient anormaux. Les incidents que MS12 laisse de côté deviennent la **cible** de MS11 —
> la boucle data-science est bouclée. »

**Positionnement honnête (à dire d'emblée) :** « MS11 ne remplace pas la déclaration du chauffeur pour un
accident évident. Sa valeur est de repérer les anomalies **non déclarées** (surcharge, lenteurs contextuelles)
et de fournir une **supervision automatique** à l'échelle de la flotte. »

---

## 1️⃣ Pipeline Data Science (3 min)

> **Support : le notebook `ms11-analytique/notebooks/04_anomaly_detection.ipynb`** (12 figures).

### a) Apprentissage non supervisé — pourquoi
> « Les incidents sont **rares** (~1 %) et **hétérogènes**. Plutôt qu'un classifieur supervisé, j'apprends à
> quoi ressemble un trajet **normal** et je signale les écarts (**Isolation Forest**). Le label `incident_type`
> ne sert **jamais à entraîner** — uniquement à **évaluer**. »

**Isolation Forest en une phrase :**
> « On coupe l'espace au hasard ; un point anormal est **isolé en très peu de coupes**. Le score = la facilité
> d'isolement. »

### b) Le vrai enjeu : le **feature engineering** (LE point à défendre)
> « Le signal naïf serait le **ratio = durée réelle / durée estimée**. Mais un ratio de 2,4 est **normal** en
> embouteillage+pluie et **anormal** par temps fluide. J'ai donc construit la feature **`surprise` = ratio
> ajusté au contexte** (trafic, météo). C'est *ça* qui fait la différence — pas le modèle. »

**3 natures d'anomalie, 3 signaux** (aucun seul ne suffit) :
| Nature | Exemple | Signal qui la trahit |
|---|---|---|
| **franche** | panne/accident (durée énorme) | `ratio` |
| **contextuelle** | lent alors que conditions légères | `surprise` |
| **surcharge** | durée ~normale mais trop de montées | `dwell` / `nb_montees` |

### c) Benchmark honnête (à montrer sur les barres du notebook)
| Détecteur | PR-AUC | Rappel | Lecture |
|---|---|---|---|
| seuil sur `ratio` brut | 0.79 | 0.75 | rate le contextuel & la surcharge |
| seuil sur `surprise` (**sans ML**) | 0.80 | 0.75 | le feature fait déjà 80 % du travail |
| Isolation Forest « tout » (dilué) | 0.48 | 0.50 | trop de features **diluent** le signal |
| **Isolation Forest curé 🏆** | **0.91** | **0.88** | combine surprise + dwell → gagne |

**La triple leçon (à énoncer) :**
> « (1) Le **feature engineering** prime. (2) La **curation** prime — trop de variables noient Isolation Forest.
> (3) Le **multivarié gagne** parce que les anomalies sont hétérogènes. »

---

## 2️⃣ Démonstration live (2 min)

> **Support : `html_tests/test-console.html` → onglet 📈 Analytique.**

1. **`model-info`** → montrer PR-AUC 0.91, rappel 0.88, détecteur `iforest_curated`.
2. **3 cas parlants** (bouton POST /anomalies) :
   | Entrée | Attendu |
   |---|---|
   | `42 min · fluide` | 🔴 **anomalie critique** (panne) |
   | `8.6 min · embouteillage + pluie` | ✅ **normal** (le contexte justifie — pas de fausse alerte) |
   | `6.5 min · 30 montées` | ⚠️ **anomalie** (surcharge, durée pourtant normale) |
3. **`scan top 10`** → liste des trajets les plus anormaux + **précision 0,70 / rappel 0,72** sur l'ensemble
   (les top anomalies sont bien de vraies pannes/accidents/surcharges).

**La phrase qui tue :**
> « Regardez : un bus lent à cause de l'embouteillage n'est **pas** signalé — le modèle ne se laisse pas piéger.
> Mais une surcharge à durée normale, **invisible pour un simple seuil**, est détectée. »

---

## 3️⃣ Questions probables du jury — réponses prêtes (les dures)

**« Pourquoi du machine learning si un simple ratio suffit à voir un retard ? »**
> Pour voir « en retard », le ratio suffit — je suis d'accord. Mais « en retard » ≠ « anormal » : un retard
> **justifié** par le trafic est normal. Mon benchmark le montre : un **seuil sur la bonne feature (`surprise`)
> fait déjà 80 %** ; le ML n'ajoute que le **dernier incrément** (0,80 → 0,91) en gérant les anomalies
> **multivariées** (surcharge). **Je ne mets pas du ML par principe** — je l'ai justifié par les chiffres.

**« Puisque c'est a posteriori, à quoi ça sert ? Le chauffeur signale déjà les incidents. »**
> Exact pour les incidents **évidents**. MS11 cible ce qui **n'est pas déclaré** (surcharges, dérives
> silencieuses), **recoupe** déclaré (MS10) vs réel, et donne des **KPIs / points noirs** à l'échelle de la
> flotte — un motif agrégé qu'aucune déclaration individuelle ne révèle.

**« Et le temps réel ? »**
> Ce n'est **pas** ce que fait MS11 aujourd'hui — c'est de l'analyse **a posteriori**, je l'assume. Le temps
> réel serait un **autre mécanisme** (comparer le temps écoulé au temps attendu de l'ETA MS12, en direct) —
> c'est ma **perspective** identifiée.

**« Vos données sont synthétiques — est-ce valide ? »**
> Le pipeline et la méthode sont **validés** ; les seuils devraient être **recalibrés sur données terrain**.
> Les incidents confirmés par l'admin (MS10) fourniraient de **vraies étiquettes** pour ré-évaluer — c'est la
> **boucle d'amélioration**.

**« Isolation Forest, concrètement ? »**
> Modèle non supervisé : des arbres isolent les points ; les anomalies sont isolées en peu de coupes → score
> élevé. Je le vois sur la **frontière de décision 2D** et la **projection PCA** du notebook.

---

## ✅ Les 3 phrases à ne PAS oublier

1. **« Le vrai levier, c'est le feature engineering (`surprise` = ratio ajusté au contexte), pas le modèle. »**
2. **« Je ne mets pas du ML par principe : le benchmark montre qu'un seuil fait 80 %, le ML ajoute le multivarié. »**
3. **« MS11 est une supervision a posteriori des anomalies NON déclarées — pas une alerte temps réel, et je l'assume. »**

---

## ⚠️ Honnêteté & limites (à assumer, ne pas cacher)
- **A posteriori** : détecte après le trajet → pas d'alerte pendant l'incident (perspective : temps réel via ETA MS12).
- **Redondant** pour les incidents évidents déjà déclarés → la valeur est sur le **non déclaré** + les **KPIs**.
- **Données synthétiques** → recalibration terrain nécessaire.

---

### 📂 Artefacts à avoir ouverts pendant la démo
- `ms11-analytique/notebooks/04_anomaly_detection.ipynb` (EDA + frontière IF + PCA + benchmark)
- `ms11-analytique/data/anomaly_benchmark.json` (les 4 détecteurs comparés)
- `ms11-analytique/data/anomaly_config.json` (modèle gelé : `iforest_curated`, seuil, métriques)
- `html_tests/test-console.html` → onglet 📈 Analytique (démo live)
- `docs/MS11_ANOMALY_DETECTION.md` (documentation détaillée, si question technique)
