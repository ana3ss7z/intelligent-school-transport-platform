# MS6 — l'algorithme de production entre enfin dans l'arène

> **Document pédagogique.** Il applique à MS6 le protocole du [benchmark CVRP](MS5_BENCHMARK_CVRP.md)
> et corrige deux défauts de méthode du dossier existant. Il confirme la thèse centrale du projet —
> mais **sur une autre métrique que celle qu'on regardait**.
>
> Code : [`ablation_distance.py`](../ms6-clustering/ablation_distance.py) ·
> Résultats : [`data/ablation_distance.json`](../ms6-clustering/data/ablation_distance.json)

---

## 1. Deux défauts de méthode, avant tout résultat

### Le benchmark ne justifiait pas le choix de production

`02_model_comparison.ipynb` compare **dix algorithmes** et couronne **OPTICS** (score composite
0,931). Or OPTICS produit ici **seize groupes** et **cinquante-deux points de bruit** : impossible
d'en faire des bus. Il « gagne » sur un score dont 30 % est la faisabilité capacitaire — qu'il
satisfait uniquement parce qu'il fabrique des mini-groupes. Le gagnant est un artefact de pondération.

Et surtout : le choix de production y est **écrit en dur** dans le notebook, et l'algorithme
réellement déployé — **k-médoïdes capacitaire routier** — **n'est dans aucun des dix**.

> Un benchmark qui n'évalue pas l'algorithme qu'on déploie ne justifie rien. Il décore.

### L'apport de la distance routière n'était pas isolé

`03_production_strategy.ipynb` compare « euclidien k=8 → 0,4213 » à « routier k=7 → 0,4334 ». Trois
facteurs changent en même temps : **la distance, l'algorithme et le nombre de bus**. Attribuer
l'écart à la distance routière est un raccourci — le gain pouvait venir du changement de `k`.

C'est d'autant plus gênant que cette thèse porte **deux** conclusions du projet : la qualité du
clustering, *et* l'explication du résultat CVRP de MS5 (« l'information géographique est injectée
avant le routage »).

---

## 2. Le protocole corrigé

| Règle | Application ici |
|---|---|
| Une seule matrice de référence | La matrice routière OSRM en cache (`osrm_dist_m.npy`, 300×300) |
| **Tout le monde noté avec la même règle** | Silhouette et compacité calculées sur la matrice **routière**, quelle que soit la distance ayant servi à *construire* la partition. Sinon chacun serait jugé à sa propre aune, et l'euclidien gagnerait mécaniquement |
| **Un seul facteur varié** | Pour l'ablation : même algorithme, même `k`, même graine — seule la matrice change |
| Des baselines naïves crédibles | Découpage par quartier, et partition aléatoire équilibrée |
| **L'algorithme de production dans l'arène** | Le vrai, et aussi le pipeline complet (`_compute_production`, appelé directement) |
| Une métrique métier | Deux, en fait — et c'est le cœur du document (§4) |

---

## 3. L'arène

Tout est évalué sur la matrice routière, à `k = 7` et capacité 50.

| Méthode | Silhouette | Compacité méd. | Taille max | Faisable | **Flotte (min)** | vs prod | **À bord moyen** | À bord p90 |
|---|--:|--:|--:|:-:|--:|--:|--:|--:|
| **k-médoïdes capacitaire ROUTIER** *(production)* | 0,4256 | 734 m | 50 | ✅ | **254,3** | — | **17,5 min** | 33,7 min |
| k-médoïdes capacitaire EUCLIDIEN | 0,4237 | 757 m | 50 | ✅ | 258,0 | +1,5 % | 19,2 min | 34,0 min |
| k-means capacitaire (euclidien) | 0,3773 | 784 m | 50 | ✅ | 250,7 | **−1,4 %** | 18,1 min | 33,8 min |
| k-means sans contrainte de capacité | 0,4636 | 739 m | **66** | ❌ | 245,6 | −3,4 % | 16,5 min | 27,3 min |
| **baseline « un bus par quartier »** | 0,0394 | 1 548 m | 46 | ✅ | 291,5 | **+14,6 %** | 22,2 min | 37,5 min |
| baseline aléatoire équilibrée | −0,0806 | 2 649 m | 43 | ✅ | 532,9 | +109,6 % | 38,6 min | 68,9 min |

**Ce que ça règle immédiatement**

- *« Votre algorithme fait-il mieux qu'un simple découpage par quartier ? »* — **Oui : 14,6 % de
  conduite en moins, et 4,7 minutes de bus en moins par enfant, chaque matin.** Le dossier n'avait
  aucune réponse à cette question jusqu'ici.
- La partition aléatoire coûte **+110 %** : la géographie est bien le premier levier, et le
  découpage par quartier en capte déjà l'essentiel. Le travail de MS6 porte sur le dernier quart.
- **Le prix de la contrainte de capacité est chiffré** : le k-means libre fait mieux partout
  (−3,4 % de flotte, −1 min à bord) mais produit un groupe de **66 élèves**. Ses chiffres sont donc
  **fictifs** — ce bus n'existe pas. C'est le seul rôle légitime de cette ligne : borner ce qu'on
  abandonne en refusant l'infaisable.

---

## 4. Le résultat qui compte : on mesurait la mauvaise chose

Comparons les deux lignes qui ne diffèrent **que** par la matrice de distances :

| | Silhouette | Flotte | **Temps à bord / enfant** |
|---|--:|--:|--:|
| k-médoïdes **routier** | 0,4256 | 254,3 min | **17,5 min** |
| k-médoïdes **euclidien** | 0,4237 | 258,0 min | 19,2 min |
| Écart | **+0,0019** | −3,7 min (−1,5 %) | **−1,7 min (−9,7 %)** |

Trois lectures d'une même expérience :

1. **En silhouette, l'effet est invisible** (0,0019). C'est l'indice que le dossier mettait en
   avant, et il ne voit rien. Il ne pouvait donc pas soutenir la thèse qu'on lui faisait porter.
2. **En temps de conduite, l'effet est réel mais modeste** : 1,5 %.
3. **En temps passé dans le bus par chaque enfant, l'effet est six fois plus grand** : **−9,7 %**,
   soit **1,7 minute par enfant et par trajet**. Sur 300 élèves et deux trajets par jour, ce sont
   **17 heures d'enfant** économisées chaque jour.

> **La distance routière ne rend pas les groupes « plus jolis ». Elle raccourcit le temps que chaque
> enfant passe dans le bus.** C'est ce que le projet cherchait à optimiser depuis le début, et c'est
> désormais mesuré au lieu d'être supposé.

### Et cela consolide le résultat du CVRP

Le [benchmark CVRP](MS5_BENCHMARK_CVRP.md) explique la victoire de la décomposition par « les
k-médoïdes travaillent déjà sur la distance routière ». On peut maintenant chiffrer cette phrase :
la distance routière vaut **1,5 % du temps de conduite total** — soit exactement l'ordre de grandeur
des écarts observés dans ce benchmark (de +0,2 % à −2,3 %). L'explication tient, et elle a une taille.

### Ce que la métrique choisie change au classement

`k-means capacitaire` a une **silhouette nettement plus faible** (0,3773 contre 0,4256) et fait
pourtant **1,4 % de conduite en moins**. Mais il fait passer **0,6 minute de plus dans le bus** à
chaque enfant. Deux métriques, deux gagnants. Il fallait donc décider **ce qu'on optimise avant de
comparer** — le projet a choisi le temps à bord, et ce choix résiste à la mesure.

---

## 5. Le pipeline complet dit autre chose que sa propre configuration gelée

Le service n'exécute pas seulement l'affectation : il enchaîne **dispersés (DBSCAN) → Pareto →
affectation LP**. En appelant `_compute_production` directement :

| Distance | k choisi | Dispersés | Silhouette | Compacité méd. | Flotte | À bord moyen |
|---|--:|--:|--:|--:|--:|--:|
| **routière** *(production)* | **8** | 17 | **0,4056** | 734 m | 259,0 min | **16,6 min** |
| euclidienne | 9 | 14 | 0,4133 | 668 m | 272,2 min | 14,2 min |

### Un défaut de cohérence, confirmé

Le fichier gelé `notebooks/production_config.json` annonce **k = 7 et silhouette 0,4334**. Le chemin
réellement exécuté produit **k = 8 et silhouette 0,4056**. Trois artefacts « de production »
coexistent d'ailleurs dans le dépôt, dont deux périmés :

| Fichier | Version | k | Silhouette | Lu par le code ? |
|---|---|--:|--:|:-:|
| `notebooks/model_metadata.json` | v2, K-Means capacitaire | 6 | 0,3754 | non |
| `notebooks/benchmark_summary.json` | choix = K-Means capacitaire | 6 | — | non |
| `notebooks/production_config.json` | v3, k-médoïdes routier | **7** | **0,4334** | **oui** |
| *chemin réellement exécuté* | v3 | **8** | **0,4056** | — |

L'écart vient de ce que la configuration gelée a été calculée sur les **283 élèves du cœur** (hors
dispersés), alors que le pipeline fixe `k_min` sur l'effectif **total** (300) et affecte tout le
monde. **Conséquence concrète : la référence du garde-fou qualité (`quality.py`) est calibrée sur un
point de fonctionnement que le service ne reproduit jamais.**

> Ce document ne corrige rien : il mesure et documente. Le correctif — recalculer
> `production_config.json` depuis le chemin réellement exécuté — est une décision de production.

### Le 8ᵉ bus achète du temps d'enfant

Notons tout de même que le pipeline complet (8 bus, 259,0 min) fait **16,6 min à bord** contre
17,5 pour la version à 7 bus. C'est **le même arbitrage que celui identifié par le benchmark CVRP** :
un bus de plus coûte du temps de flotte et rend du temps aux familles. La cohérence de
l'architecture se vérifie donc dans les deux sens.

---

## 6. Les écarts de silhouette entre `k` voisins ont-ils un sens ?

Tout le service est figé à `random_state = 42`. Dix graines, k-médoïdes routier :

| k | Silhouette moyenne | Écart-type | Min | Max |
|--:|--:|--:|--:|--:|
| 6 | 0,3511 | 0,0001 | 0,3510 | 0,3513 |
| **7** | **0,4257** | **0,0001** | 0,4256 | 0,4258 |
| 8 | 0,4088 | 0,0119 | 0,3958 | 0,4433 |
| 9 | 0,4169 | 0,0204 | 0,3906 | 0,4599 |

- **k = 7 est remarquablement stable** (±0,0001) et domine k = 8 et k = 9 : le choix gelé est,
  lui, bien fondé.
- En revanche **k = 8 et k = 9 sont instables** (±0,012 et ±0,020) : leurs 0,006 d'écart, présentés
  comme des différences dans le dossier, sont **du bruit d'initialisation**. Il ne fallait pas les
  départager sans variance.
- Et c'est **k = 8 que le pipeline choisit** — donc le point de fonctionnement le moins reproductible.

---

## 7. Verdict

**Confirmé**
- La distance routière apporte un gain **réel** : −1,5 % de conduite et surtout **−9,7 % de temps à
  bord par enfant**, à algorithme et `k` constants — enfin une ablation propre.
- Le k-médoïdes capacitaire routier **bat toutes les baselines faisables** sur le temps à bord.
- Le choix de `k = 7` dans la configuration gelée est solide et stable.

**Infirmé / à nuancer**
- La silhouette **ne voit pas** l'apport de la distance routière (+0,0019). L'indice interne mis en
  avant dans le dossier n'était pas le bon instrument.
- « OPTICS gagne le benchmark » n'a aucune portée : il est infaisable, et le vrai algorithme n'y
  figurait pas.
- Les écarts de silhouette entre k=8 et k=9 étaient dans le bruit.

**À corriger (décision de production)**
1. Réconcilier `production_config.json` (k=7 / 0,4334) avec le chemin exécuté (k=8 / 0,4056), et
   recalibrer la référence de `quality.py` en conséquence.
2. Supprimer ou archiver `model_metadata.json` et `benchmark_summary.json`, périmés et contradictoires.

---

## 8. Reproduire

`OSRM` doit tourner (`docker start osrm_meknes`) : la matrice élèves↔élèves est en cache, mais la
ligne du **dépôt** (école ↔ chaque élève) est récupérée à la volée — par blocs de 90 coordonnées,
le plafond de 100 de `/table` étant le même piège que celui rencontré dans le benchmark CVRP.

```bash
cd ms6-clustering
python ablation_distance.py      # → data/ablation_distance.json
```

Le TSP aval s'est révélé **parfaitement déterministe** sur ces instances (5 exécutions, écart-type
0,00 min) : les écarts de 1,4 % rapportés ici ne sont pas du bruit de solveur — contrôle effectué.

## 9. Ce qui reste non vérifié

- **Une seule instance** : 300 élèves, une école, capacité 50. Aucune étude de passage à l'échelle
  (le LP construit `n × k` variables) ni de sensibilité à la capacité.
- Les durées de tournée supposent **zéro temps d'arrêt** aux points de ramassage ; le temps à bord
  réel est donc supérieur, mais le biais est identique pour toutes les méthodes comparées.
- La matrice routière en cache est **symétrisée** (`(D + Dᵀ)/2`) par MS6 pour ses k-médoïdes.
  L'erreur introduite n'est pas quantifiée ici — alors qu'elle l'a été pour MS5, où l'asymétrie
  s'est révélée décisive.
- Le découpage par quartier utilise un empilage glouton ; un exploitant humain ferait sans doute
  mieux à la marge.
