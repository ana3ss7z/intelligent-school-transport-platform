# Protocole de benchmark des briques IA

> **Le document méthodologique du projet.** Il énonce les règles auxquelles les cinq briques IA ont
> été soumises, et rassemble les verdicts. C'est lui qui transforme cinq notebooks en **une démarche**.
>
> Benchmarks détaillés : [MS5 — CVRP](MS5_BENCHMARK_CVRP.md) ·
> [MS6 — distance routière](MS6_BENCHMARK_DISTANCE.md) ·
> [MS11 — règles live](MS11_BENCHMARK_REGLES_LIVE.md) ·
> [MS12 — garde et ablation](MS12_BENCHMARK_GARDE_ET_ABLATION.md) ·
> [MS9 — évaluation LLM](MS9_EVALUATION.md)

---

## 1. Pourquoi un protocole, et pas cinq notebooks

Un projet de data science se juge moins sur ses résultats que sur la **manière dont ils ont été
obtenus**. Un chiffre flatteur sans protocole ne prouve rien ; un chiffre décevant obtenu proprement
est une contribution.

Le premier benchmark rigoureux du projet — [CVRP global contre MS6+TSP](MS5_BENCHMARK_CVRP.md) — a
produit un résultat inattendu : la décomposition ne coûte rien. Mais il a surtout produit une
**méthode**. Cette méthode a ensuite été appliquée aux quatre autres briques, et elle a chaque fois
trouvé quelque chose que le dossier ne savait pas.

---

## 2. Les six règles

### Règle 1 — La question doit pouvoir se répondre dans les deux sens

Avant de mesurer, on écrit ce qu'on conclura **si le résultat est l'inverse de celui espéré**. Si on
ne sait pas répondre, ce n'est pas un benchmark, c'est une justification.

> *Sinon :* on obtient un « benchmark » dont la conclusion était écrite d'avance.
> *Exemple :* si le CVRP avait nettement gagné, on chiffrait le coût de notre architecture ; il a
> perdu, on l'a gardé comme outil de dimensionnement de flotte.

### Règle 2 — Un challenger crédible, et l'algorithme de production dans l'arène

Battre `DummyRegressor` ne prouve rien. Et surtout : **l'algorithme qu'on déploie doit figurer dans
la comparaison**.

> *Sinon :* on élit un gagnant qu'on ne déploie pas.
> *Exemple :* MS6 comparait dix algorithmes et couronnait OPTICS — qui produit seize mini-groupes
> inutilisables — pendant que le k-médoïdes capacitaire routier réellement déployé n'était **dans
> aucun des dix**.

### Règle 3 — Protocole égalisé, et un seul facteur varié

Mêmes données, même grandeur mesurée, même budget de calcul, même arrondi. Et pour une ablation :
**une seule chose change à la fois**.

> *Sinon :* on attribue à un facteur un gain qui venait d'un autre.
> *Exemples :* MS6 comparait « euclidien k=8 » à « routier k=7 » — trois facteurs simultanés.
> MS11 : unir deux détecteurs en doublant le nombre d'alertes n'aurait rien prouvé, l'union a donc
> été calibrée par dichotomie pour émettre **exactement** autant d'alertes qu'un détecteur seul.
> MS9 : la cascade de modèles est **neutralisée** pendant la mesure, sinon un modèle saturé serait
> silencieusement remplacé et l'on mesurerait un mélange.

### Règle 4 — Tout le monde est noté avec la même règle

Chaque candidat est évalué avec **la métrique de référence**, pas avec celle qui l'avantage.

> *Sinon :* chacun est jugé à sa propre aune.
> *Exemple :* dans MS6, les partitions construites en distance euclidienne sont évaluées sur la
> matrice **routière**, comme les autres. Sans cela l'euclidien gagnerait mécaniquement.

### Règle 5 — Des métriques opérationnelles, et la bonne métrique métier

Le temps de calcul, la robustesse et le coût font partie du verdict. Et il faut décider **ce qu'on
optimise avant de comparer**.

> *Sinon :* on élit un gagnant inexploitable, ou on mesure la mauvaise chose.
> *Exemples :* MS11 mesure les **fausses alarmes par heure** — une alerte qui crie au loup est
> désactivée en trois jours, quelle que soit sa PR-AUC. MS6 a révélé que la silhouette et le temps
> de conduite **désignent deux gagnants différents** : il fallait trancher, et le projet optimise le
> **temps passé dans le bus par chaque enfant**.

### Règle 6 — Énoncer l'incertitude et le régime de validité

Un écart doit être accompagné de sa variabilité, et un résultat de ses limites.

> *Sinon :* on défend 2,7 secondes d'écart comme un résultat, ou quatre décimales de PR-AUC sur huit
> observations.
> *Exemples :* MS11 — sous validation glissante, le classement des détecteurs **s'inverse**.
> MS12 — le bootstrap apparié montre au contraire que l'écart de 2,7 s **est** significatif :
> l'incertitude ne va pas toujours dans le sens qu'on croit.

### Corollaire — Le perdant est reclassé, pas jeté

Un benchmark produit deux informations : qui gagne, et à quoi sert l'autre.

> *Exemple :* le CVRP perd en temps de conduite mais trouve une solution à **6 bus au lieu de 7**.
> Il devient l'outil de **dimensionnement de flotte** du projet.

---

## 3. Ce que le protocole a trouvé

Chaque brique a été passée au même filtre. **Dans les cinq cas, la mesure a contredit ou nuancé une
affirmation du dossier.**

### Le défaut structurel, commun à trois briques

> **Ce qui tournait en production n'était pas ce qui avait été benchmarké.**

| Brique | Ce qui était mesuré | Ce qui tourne réellement |
|---|---|---|
| **MS6** | dix algorithmes euclidiens | k-médoïdes capacitaire **routier** — absent du benchmark |
| **MS11** | Isolation Forest sur trajets complets, à la demande | trois **règles de seuil** sur chaque ping GPS — aucune métrique |
| **MS12** | régression sur tronçons de 0,7–4 km | mode **`facteur_contexte`** à 6–12 km — aucune métrique |

C'est le défaut le plus instructif du projet, et il n'était visible qu'en se demandant *« quel code
s'exécute quand un parent ouvre l'application ? »* plutôt que *« quel notebook ai-je écrit ? »*.

### Les résultats, brique par brique

| Brique | Question tranchée | Verdict mesuré |
|---|---|---|
| **MS5** | La décomposition MS6→TSP coûte-t-elle du temps de conduite ? | **Non** : à budget égal le CVRP ne gagne jamais plus de 0,2 % et perd jusqu'à 2,3 %. Reclassé en outil de dimensionnement (6 bus au lieu de 7) |
| **MS6** | La distance routière vaut-elle son coût ? | **Oui, mais pas là où on regardait** : +0,002 de silhouette (invisible), −1,5 % de conduite, et **−9,7 % de temps à bord par enfant**. Le naïf « un bus par quartier » coûte **+14,6 %** |
| **MS11** | Les règles live détectent-elles ? Le multivarié gagne-t-il ? | **Règles : partiellement** — la déviation est aveugle sur 70 % du parcours. **Multivarié : non** — sous validation glissante le seuil univarié `surprise` passe devant (0,926 vs 0,847) |
| **MS12** | La garde anti-extrapolation vaut-elle mieux qu'extrapoler ? | **Oui, nettement** : −37 % d'erreur contre l'extrapolation, −77 % contre OSRM brut. Et le gagnant ElasticNet **résiste** au réglage de XGBoost |
| **MS9** | La cascade de modèles est-elle le bon choix ? | *voir [MS9_EVALUATION.md](MS9_EVALUATION.md)* |

---

## 4. Les trois enseignements transversaux

### a) La métrique décide du gagnant — il faut donc la choisir avant

Dans MS6, la silhouette classe le k-médoïdes routier **devant** le k-means capacitaire (0,4256 contre
0,3773), tandis que le temps de conduite les classe **dans l'autre sens** (254,3 contre 250,7 min).
Aucun des deux chiffres n'est faux. Ce qui manquait, c'était la décision explicite : le projet
optimise le **temps à bord par enfant**, et c'est sur cette métrique-là que sa solution gagne.

### b) L'importance n'est pas l'ablation

Dans MS12, `duree_moyenne_historique_s` est la **7ᵉ importance publiée** (coefficient 0,333). Son
ablation coûte **0,003 minute** — rien. À l'inverse, retirer le `dwell` **améliore** le modèle.
Une importance dit ce que le modèle *utilise* ; seule l'ablation dit ce qu'il *perdrait*.

### c) La taille de l'échantillon décide de la conclusion

Dans MS11, le classement des détecteurs repose sur **huit** anomalies de test. Le bootstrap donne
des intervalles de confiance qui se recouvrent largement ; la validation glissante, qui porte
l'effectif à 38, **inverse le gagnant**. La leçon vaut au-delà de MS11 : la première question à
poser devant un classement, c'est *combien d'observations le départagent ?*

---

## 5. Ce que ce protocole ne couvre pas

Ces limites valent pour les cinq briques et doivent être énoncées d'emblée.

- **Aucune donnée terrain.** MS12 et MS11 reposent sur des générateurs ancrés sur de l'OSRM réel,
  mais simulés. MS6 et MS5 utilisent de vraies coordonnées et de vraies routes, mais une seule
  instance : 300 élèves, une école.
- **Circularité assumée pour MS12** : les données sont produites par une formule multiplicative,
  qu'un modèle linéaire sur variables indicatrices retrouve presque exactement. La victoire
  d'ElasticNet est en partie inscrite dans le générateur — le protocole reste valide, la
  généralisation à des durées GPS réelles n'est pas testée.
- **Une seule graine de génération** pour MS11 et MS12 : le classement n'a pas été rejoué sur un
  autre tirage.
- **Pas de passage à l'échelle** : aucune brique n'a été testée au-delà de son instance nominale.

---

## 6. Reproduire l'ensemble

```bash
# Hors ligne — aucune dépendance
cd ms11-analytique && python replay.py && python ablation_anomaly.py
cd ms12-prediction && python ablation.py
cd ms9-llm        && pytest tests -q && python eval/rapport_sql_guard.py

# OSRM requis (docker start osrm_meknes)
cd ms6-clustering    && python ablation_distance.py
cd ms5-planification && python -m jupyter nbconvert --execute --to notebook \
                          --inplace notebooks/06_cvrp_benchmark.ipynb

# Backend complet + clés LLM
cd ms9-llm && python eval/runner.py && python eval/runner_admin.py
```

**Aucun de ces scripts ne modifie la production.** Les artefacts gelés (`eta_model.pkl`,
`eta_config.json`, `anomaly_model.pkl`, `production_config.json`) sont lus, jamais réécrits — un
`git status` le vérifie après coup.
