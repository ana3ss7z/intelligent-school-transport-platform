# MS12 — mesurer ce que le service fait vraiment

> **Document pédagogique.** Il applique à MS12 le protocole du [benchmark CVRP](MS5_BENCHMARK_CVRP.md).
> Il valide la décision la plus subtile du projet — qui n'avait **aucune mesure** — et met au jour
> une amélioration de 15 % restée sur la table.
>
> Code : [`ablation.py`](../ms12-prediction/ablation.py) ·
> Résultats : [`data/ablation/resultats.json`](../ms12-prediction/data/ablation/resultats.json)
> **Aucun artefact gelé n'a été modifié** (`eta_model.pkl`, `eta_config.json` — vérifié par `git status`).

---

## 1. Le mode qui tourne en production n'avait aucune métrique

Le modèle est entraîné sur des **tronçons** entre deux arrêts : 0,7 à 4,0 km. Mais depuis que les
applications demandent l'ETA de la **tournée restante**, l'entrée fait 6 à 12 km. `predire_minutes`
bascule alors sur un mode de repli, `facteur_contexte`, dont le principe est :

> **le modèle dit de combien ça se dégrade aujourd'hui ; OSRM dit la distance.**

Concrètement : on interroge le modèle sur un tronçon **de référence** (la médiane d'entraînement)
avec le **contexte réel du moment**, on en déduit un facteur d'inflation, et on l'applique à la
durée OSRM restante. Le modèle ne quitte jamais son domaine.

Le docstring l'admettait lui-même : *« les métriques publiées (MAE 1,32 min) n'y valent plus rien »*.
**Et rien ne les remplaçait.**

### Construire une vérité terrain sans rien inventer

Un trajet entier **est** la concaténation de ses tronçons. Sa distance est leur somme, sa durée
réelle aussi. En agrégeant le dataset existant par (date, moment, circuit), on obtient **180 trajets
de test de 6 436 à 11 775 m** — exactement le régime de production — produits par les **mêmes lois**
que l'entraînement, sans régénérer quoi que ce soit ni supposer une extrapolation des facteurs.

### Résultat : la garde est largement validée

Sur les 173 trajets **normaux** de la période de test (les 180 sont tous traités en mode
`facteur_contexte`, donc c'est bien le chemin de production qui est mesuré) :

| Estimateur | MAE (min) | RMSE | R² | MAPE | Biais |
|---|--:|--:|--:|--:|--:|
| **`facteur_contexte`** *(production)* | **2,174** | **2,581** | **0,826** | **9,2 %** | +1,661 |
| modèle extrapolé hors domaine | 3,448 | 4,331 | 0,509 | 13,6 % | −0,354 |
| OSRM brut (baseline métier) | 9,331 | 10,846 | **−2,077** | 34,3 % | −9,331 |

- **−37 % d'erreur par rapport à l'extrapolation directe.** La garde n'est donc pas une précaution
  cosmétique : extrapoler coûterait 1,3 minute d'erreur par trajet.
- **−77 % par rapport à OSRM brut**, dont le R² négatif signifie qu'il fait *pire que prédire la
  moyenne*. Sur une tournée entière, OSRM sous-estime de **9,3 minutes** en moyenne.
- Sur l'ensemble des 180 trajets (incidents compris) : 3,925 contre 5,198 et 11,133 — même ordre.

> **La décision la plus subtile du projet était aussi la seule sans preuve. Elle en a une maintenant,
> et elle est nette.**

### Un défaut à signaler quand même

Deux réserves, l'une chiffrée, l'autre structurelle :

1. **`facteur_contexte` sur-prédit de 1,66 minute** en moyenne (contre −0,35 pour l'extrapolation).
   Annoncer un bus plus tard qu'il n'arrive est le bon sens de l'erreur pour une famille, mais c'est
   un biais, et il est corrigeable (voir §4).
2. **`domaine_entrainement` vaut `null` dans `eta_config.json`.** L'artefact gelé est antérieur à la
   garde. `ETAModel.load()` retombe donc sur `_domaine_depuis_dataset()`, qui **relit le CSV
   d'entraînement au démarrage**. Si ce fichier est absent du déploiement, la fonction renvoie `{}`,
   `hors_domaine` devient toujours faux, et **le service extrapole en silence** — exactement ce que
   la garde existe pour empêcher. Il faudrait geler ces bornes dans le JSON.

---

## 2. Le gagnant tient à 2,7 secondes — est-ce un vrai gagnant ?

ElasticNet l'emporte avec un MAE de 1,3219 contre 1,3668 pour Ridge : **0,045 minute, soit 2,7
secondes**, sur 720 points dont 1 % d'incidents à ±100 minutes. Sans intervalle de confiance, ce
classement n'était pas défendable.

**Bootstrap apparié** (5 000 tirages, mêmes indices pour les deux modèles — c'est l'appariement qui
donne la puissance, puisque les erreurs sont fortement corrélées d'un modèle à l'autre) :

| Challenger | MAE | Δ MAE | IC 95 % de la différence | Significatif à 5 % |
|---|--:|--:|---|:-:|
| ridge | 1,3668 | +0,0449 | [+0,0197 ; +0,0697] | ✅ |
| linear | 1,3674 | +0,0455 | [+0,0202 ; +0,0705] | ✅ |
| knn | 1,4515 | +0,1296 | [+0,0468 ; +0,2156] | ✅ |
| gradient_boosting | 1,4756 | +0,1537 | [+0,0561 ; +0,2716] | ✅ |
| extra_trees | 1,5486 | +0,2268 | [+0,0136 ; +0,4754] | ✅ |
| random_forest | 1,5666 | +0,2447 | [+0,0833 ; +0,4225] | ✅ |
| xgboost | 1,6729 | +0,3511 | [+0,1737 ; +0,5454] | ✅ |
| hist_gb | 1,7052 | +0,3833 | [+0,2827 ; +0,4917] | ✅ |
| lightgbm | 1,9259 | +0,6040 | [+0,4706 ; +0,7447] | ✅ |
| baseline_osrm | 2,7957 | +1,4738 | [+1,3429 ; +1,6016] | ✅ |

**Les dix intervalles sont entièrement positifs : ElasticNet bat significativement tout le monde.**

*Note d'honnêteté : nous attendions l'inverse.* Un écart de 2,7 secondes ressemble à du bruit — mais
le test apparié compare les erreurs **sur les mêmes trajets**, et l'écart est systématique, pas
aléatoire. La mesure a corrigé notre intuition, ce qui est exactement son rôle.

### Et si les arbres perdaient parce qu'ils étaient mal réglés ?

C'était l'objection sérieuse : les onze candidats tournaient avec leurs **hyperparamètres par
défaut**. `RandomizedSearchCV` (25 tirages, `TimeSeriesSplit` à 3 replis — validation **temporelle**,
jamais aléatoire, sinon on entraînerait sur le futur) :

| Modèle | MAE test par défaut | MAE test **réglé** |
|---|--:|--:|
| xgboost | 1,6729 | **1,3945** |
| random_forest | 1,5666 | **1,4052** |
| elasticnet *(rien à régler)* | 1,3219 | 1,3219 |

Le réglage fait gagner **17 % à XGBoost** — l'objection était donc légitime. Mais il reste derrière.
**La conclusion « le linéaire gagne » survit à un protocole équitable.**

---

## 3. La baseline que tout le monde aurait demandée

Le dossier compare à **OSRM brut**. Mais la vraie baseline d'un exploitant, c'est *« ce qu'a duré ce
tronçon les jours précédents »* — un tableur suffit. Cette moyenne existait déjà comme **feature**
(`duree_moyenne_historique_s`), jamais comme **prédicteur autonome**.

| Prédicteur | MAE normaux | R² normaux |
|---|--:|--:|
| ElasticNet | **0,859** | 0,820 |
| **Moyenne historique par (circuit, moment, tronçon)** | **1,523** | 0,458 |
| OSRM brut | 2,324 | −0,252 |

**Le gain réel du ML est donc de 44 %, pas de 52,7 %.** Le chiffre publié est exact, mais il est
mesuré contre la baseline *la plus faible des deux*. Annoncer 44 % contre la moyenne historique est
un argument plus fort, parce que c'est la comparaison qu'un jury ferait spontanément.

---

## 4. Un gain de 15 % laissé sur la table

Le notebook `03_production_strategy.ipynb` affiche `résidu normaux : moyenne = 0,550` sans le
commenter. Or le MAE des trajets normaux vaut 0,859 : **les deux tiers de l'erreur moyenne sont un
décalage constant**, donc corrigeable par une soustraction.

Correction estimée **sur le train uniquement** (la calibrer sur le test serait tricher) : **+0,515 min**.

| Vue | MAE avant | MAE après | Biais avant | Biais après |
|---|--:|--:|--:|--:|
| trajets normaux | 0,8590 | **0,7332** | +0,5495 | +0,0342 |
| tous trajets | 1,3219 | **1,2023** | +0,0729 | −0,4424 |

**−14,6 % de MAE sur les trajets normaux, pour une constante.** Le gain publié passerait de 52,7 % à
59,4 % contre OSRM.

> Attention au revers, et il est instructif : sur **tous** les trajets, le biais passe de +0,07 à
> −0,44. La sur-prédiction moyenne sur les trajets normaux **compense** la sous-prédiction massive
> des incidents. Corriger l'une découvre l'autre. C'est un arbitrage, pas un correctif gratuit —
> raison de plus pour le décider explicitement plutôt que de le subir.

---

## 5. Ablation : ce que le modèle perdrait, pas ce qu'il utilise

Les « importances » publiées sont des **|coefficients| standardisés**. Elles disent ce que le modèle
*utilise*, pas ce qu'il *perdrait* sans. On retire donc chaque famille et on **réentraîne** :

| Variante | Features | MAE normaux | Perte |
|---|--:|--:|--:|
| modèle complet | 26 | 0,8590 | — |
| sans **conditions** (météo + trafic) | 18 | 1,3357 | **+0,4768** |
| sans **contexte marocain** (ramadan + souk) | 24 | 0,9628 | **+0,1038** |
| sans **route** (distance, durée, feux, oued) | 22 | 0,9525 | +0,0936 |
| sans **travaux** | 25 | 0,9501 | +0,0912 |
| sans **historique** | 24 | 0,8623 | +0,0033 |
| sans **temporel** (heure, jour, mois) | 21 | 0,8530 | **−0,0060** |
| sans **dwell** (montées, descentes, occupation) | 22 | 0,8377 | **−0,0212** |

**Trois enseignements**

1. **Météo et trafic portent l'essentiel** : les retirer dégrade le MAE de 55 %. Tout le reste est
   marginal en comparaison.
2. **« Vos variables Ramadan et jour de souk servent-elles à quelque chose ? »** — oui, **+0,10 min**
   si on les enlève, soit 12 % du MAE. Le contexte marocain n'est pas un ornement. La question
   viendra, la réponse est chiffrée.
3. **Deux familles sont inutiles, voire nuisibles** : retirer le `dwell` **améliore** le modèle
   (−0,021) et retirer le `temporel` aussi (−0,006). Le modèle pourrait perdre **10 de ses 26
   variables** et faire légèrement mieux. Et `duree_moyenne_historique_s`, **7ᵉ importance publiée**
   (0,333), ne vaut que **0,003** en ablation — la démonstration la plus nette que l'importance et
   l'ablation ne mesurent pas la même chose.

---

## 6. La limite qu'il faut énoncer soi-même

Les données sont générées par une formule **multiplicative** :

```
durée = durée_base_OSRM × f_trafic × f_météo × f_ramadan × f_souk × f_travaux + dwell + bruit
```

avec seulement **12 valeurs distinctes** de `duree_base_s`. Un modèle **linéaire sur variables
indicatrices** retrouve cette structure presque exactement — la victoire d'ElasticNet est donc en
partie **inscrite dans le processus générateur**. Aucun notebook ne le disait.

Ce que cela n'invalide pas :
- le **protocole** (split temporel, baselines, ablation, réglage, significativité) reste valide ;
- la **garde `facteur_contexte`** est validée quel que soit le modèle sous-jacent — elle porte sur
  le domaine d'entrée, pas sur la famille de modèles ;
- l'**ablation** reste informative : elle dit quels facteurs le générateur a réellement injectés.

Ce que cela invalide : toute affirmation du type *« le linéaire bat le boosting sur les données de
transport »*. Sur **ces** données, oui. Sur des durées GPS réelles, non testé.

> Le déclarer soi-même désamorce la question la plus dangereuse du jury et prouve qu'on comprend son
> propre protocole. C'est plus solide que d'attendre qu'on le trouve.

---

## 7. Verdict

**Confirmé**
- `facteur_contexte`, le mode réellement exécuté, est **37 % meilleur que l'extrapolation** et
  **77 % meilleur qu'OSRM brut** sur des trajets entiers. La garde était la bonne décision.
- ElasticNet bat **significativement** les neuf challengers, y compris **après réglage** de XGBoost
  et RandomForest.
- Les variables de contexte marocain apportent **+12 % de MAE** — mesuré.

**Corrigé / nuancé**
- Le gain réel est de **44 % contre la moyenne historique**, pas 52,7 % (mesuré contre une baseline
  plus faible).
- L'écart ElasticNet/Ridge, qu'on croyait dans le bruit, est **significatif**.
- Le `dwell`, le `temporel` et l'`historique` ne servent à rien, voire nuisent.

**À décider (production)**
1. **Geler `domaine_entrainement` dans `eta_config.json`** — aujourd'hui `null`, la garde dépend de
   la présence du CSV d'entraînement au démarrage, et se désarme en silence sans lui.
2. Corriger le biais constant de **+0,515 min** (−15 % de MAE sur les trajets normaux), en assumant
   qu'il déplace le biais global vers la sous-prédiction.
3. Envisager de retirer 10 features inutiles.

> Aucun de ces points n'a été appliqué ici.

---

## 8. Reproduire

Aucun service à allumer.

```bash
cd ms12-prediction
python ablation.py       # → data/ablation/resultats.json
git status ms12-prediction/data/     # doit ne montrer que data/ablation/
```

`xgboost` et `lightgbm` sont optionnels : sans eux, les lignes correspondantes disparaissent des
tableaux, le reste est inchangé.

## 9. Ce qui reste non vérifié

- **Zéro donnée terrain.** Tout repose sur un générateur ancré sur des durées OSRM réelles, mais
  simulé. La validité prédictive réelle demande une collecte GPS.
- **Un seul jeu de données** (`seed=42`) : le classement des modèles n'a pas été rejoué sur un autre
  tirage du générateur.
- **Pas de validation croisée temporelle** sur le classement principal (un seul bloc de test de 30
  jours), contrairement à ce qui a été fait pour MS11 — où cela avait changé le gagnant. C'est la
  vérification la plus utile qui reste à faire ici.
- L'intervalle d'incertitude renvoyé par l'API (`eta ± MAE global`) reste un intervalle **non
  calibré** : ni couverture vérifiée, ni régression quantile.
