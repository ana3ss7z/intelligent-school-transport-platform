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

## 5. Le nombre de bus dépend de l'ordre des lignes

> ⚠️ **Cette section a été réécrite le 24/08. Sa première version affirmait que le pipeline
> produisait `k = 8` là où la configuration gelée annonce `k = 7`, et y voyait un défaut de
> cohérence. C'était faux, et l'erreur venait de ce benchmark, pas du service.** L'utilisateur a
> relancé le clustering et obtenu `k = 7`. La cause est plus grave que ce qui était écrit, et
> l'analyse corrigée est ci-dessous.

### Ce qui s'était passé

J'appelais bien `_compute_production`, la vraie fonction de production — mais en lui donnant les
élèves **dans l'ordre du CSV, trié par id**. Le service, lui, les reçoit dans l'ordre que MS2 lui
renvoie : `repo.findAll()` **sans `ORDER BY`**, donc l'ordre du tas PostgreSQL. J'ai exécuté la
fonction de production **sans emprunter le chemin de production** — exactement le piège n° 16 de
`CLAUDE.md`, retourné contre le benchmark lui-même.

### Le vrai défaut, mesuré

Mêmes 300 élèves, même graine, même matrice OSRM. Seul l'ordre des lignes change,
**30 permutations** :

| k retenu | occurrences | part |
|--:|--:|--:|
| **7 bus** | 17 | **57 %** |
| 8 bus | 2 | 7 % |
| **9 bus** | **11** | **37 %** |

Silhouette finale : min 0,3960 · médiane 0,4054 · max 0,4259 · σ 0,0084.
*(Données brutes : [`data/sensibilite_ordre.json`](../ms6-clustering/data/sensibilite_ordre.json).)*

> **Le nombre de bus n'est pas une propriété des données.** Il varie de 7 à 9 — deux bus et deux
> chauffeurs — selon l'ordre dans lequel PostgreSQL rend les lignes. Et mon `k = 8` était le cas le
> plus **rare** des trois : j'avais mis en avant l'exception.

L'ordre trié par id donne `k = 8` ; plusieurs permutations donnent exactement la partition observée
en production, `[50, 50, 50, 43, 42, 36, 29]` à 0,405. **Le service a raison, le benchmark avait tort.**

### La cause : un argmax sur du bruit

`choisir_k` retient le `k` de meilleure silhouette parmi les candidats du Pareto. Or la section 6
mesure la variabilité de ces silhouettes :

| k | silhouette | écart-type |
|--:|--:|--:|
| 7 | 0,4257 | **±0,0001** |
| 8 | 0,4088 | ±0,0119 |
| 9 | 0,4169 | ±0,0204 |

Les écarts entre `k` voisins (0,006 à 0,017) sont **du même ordre que le bruit** de k=8 et k=9.
L'argmax départage donc des valeurs indiscernables : selon le tirage, k=8 sort à 0,4246 ou 0,4387,
et bascule le verdict. **Le mécanisme était déjà mesuré dans ce document, section 6 — et n'avait pas
été relié à la section 5.** C'est une faute d'analyse, pas une donnée manquante.

### Pourquoi c'est bien plus qu'un problème de reproductibilité

MS6 recalcule sur `eleve.created`, `eleve.gps.updated`, `eleve.deleted`, `bus.created`,
`bus.deleted`. Et à chaque application, il **réécrit les 300 lignes** par bulk update — ce qui
change l'ordre du tas PostgreSQL. **La boucle se referme sur elle-même : appliquer un clustering
peut changer le nombre de bus du clustering suivant, sans qu'aucune donnée métier n'ait bougé.**
Une inscription en cours d'année — le cas normal dans une école — devient un tirage au sort sur la
flotte, et fait potentiellement changer de bus des enfants dont rien n'a changé.

### Ce qui reste vrai de l'ancienne section

- **Trois artefacts « de production » contradictoires** coexistent toujours, sans rapport avec l'ordre :

| Fichier | Version | k | Silhouette | Lu par le code ? |
|---|---|--:|--:|:-:|
| `notebooks/model_metadata.json` | v2, K-Means capacitaire | 6 | 0,3754 | non |
| `notebooks/benchmark_summary.json` | choix = K-Means capacitaire | 6 | — | non |
| `notebooks/production_config.json` | v3, k-médoïdes routier | **7** | **0,4334** | **oui** |

- **La référence de `quality.py` est mal calibrée, mais pas pour la raison écrite** : le 0,4334
  gelé est la silhouette du **cœur** (283 élèves, ligne Pareto k=7), tandis que le service publie
  ≈ **0,405**, la silhouette **finale** après affectation des 17 dispersés. Deux grandeurs
  différentes, toutes deux correctes — mais `quality.py` compare la seconde à la première.

### ✅ Correctif appliqué le 24/08 — résultats mesurés

| | Avant | **Après** |
|---|--:|--:|
| `k` sur 30 permutations | 7 (57 %) · 8 (7 %) · **9 (37 %)** | **7 dans 30 cas sur 30** |
| Partitions distinctes sur 30 ordres | plusieurs | **1** *(strictement reproductible)* |
| Churn moyen par inscription | 7,24 % | **2,49 %** |
| Churn médian | 6,42 % | **1,02 %** |
| Churn maximum | 13,27 % | **7,43 %** |
| Changements de flotte sur 15 inscriptions | **9** | **0** |
| Temps de calcul | 0,31 s | 1,3 s |

**Vérifié de bout en bout par le vrai chemin** (`ms2_client.get_all_eleves()`, la règle 7 du
protocole) : MS2 renvoie bien une liste **non triée**, et l'ordre MS2 comme l'ordre inversé
produisent des **affectations identiques élève par élève**.

⚠️ **Coût unique au déploiement : 22 élèves sur 300 (7,3 %) changent de bus au premier recalcul.**
La partition livrée est désormais le meilleur de 5 redémarrages, d'où une silhouette qui passe de
0,405 à **0,4256** — meilleure, mais différente. Les recalculs suivants ne déplacent plus qu'≈ 1 %.

Trois erreurs de conception ont été commises **pendant** le correctif et corrigées par la mesure ;
elles sont documentées dans `CLAUDE.md` (piège n° 19) et dans les docstrings de `selection.py` :
ε global au lieu de ε par comparaison · meilleur essai au lieu de la médiane pour comparer les `k`
(qui favorise le candidat le plus bruité : k=9 dans 14 cas sur 30) · une seule marge pour deux
questions distinctes (précision de mesure ≠ seuil métier de redistribution).

**Code** : [`selection.py`](../ms6-clustering/selection.py) ·
[`clustering.py`](../ms6-clustering/clustering.py) · [`etat.py`](../ms6-clustering/etat.py) ·
**63 tests** dans [`tests/`](../ms6-clustering/tests/).

### Les correctifs, mesurés avant d'être recommandés

Deux candidats ont été évalués — sans rien modifier en production
([`stabilite.py`](../ms6-clustering/stabilite.py), résultats dans
[`data/stabilite.json`](../ms6-clustering/data/stabilite.json)).

**A. Une règle de choix robuste.** Pour chaque `k` : **médiane** de la silhouette sur plusieurs
initialisations, puis on retient le **plus petit `k` à moins de ε = 0,02 du meilleur** (parcimonie,
dans l'esprit de la « 1-SE rule »). Un `k` instable ne peut plus gagner sur un coup de chance, et à
qualité indiscernable on préfère un bus de moins — donc un chauffeur de moins.

> Résultat : **k = 7 sur 15 permutations sur 15.** La loterie disparaît, et la sortie reste celle
> que le service produit déjà — **le correctif stabilise sans changer le comportement**.

**B. Le churn : ce que coûte une inscription en cours d'année.** On inscrit les élèves deux par deux
de 270 à 300, chaque règle choisissant librement son `k`, et on mesure le **pourcentage d'élèves qui
changent de bus** entre deux recalculs. *(Les étiquettes de groupe étant arbitraires, elles sont
appariées par recouvrement maximal — affectation hongroise — avant comptage.)*

| | Règle actuelle | Règle robuste | **Robuste + hystérésis** |
|---|--:|--:|--:|
| Churn **médian** par inscription | 6,42 % | 1,03 % | **1,01 %** |
| Churn **moyen** | 7,24 % | 5,05 % | **2,25 %** |
| Churn **maximum** | 13,27 % | 25,37 % | **8,03 %** |
| Changements de `k` sur 15 pas | **9** | 4 | **2** |
| Plage de `k` | 7 → 9 | 6 → 8 | 7 → 8 |

**La règle actuelle ne se stabilise jamais** : `k` fait 7 → 9 → 7 → 8 → 7 → 9 … neuf fois en quinze
inscriptions, et chaque bascule déplace **12 à 13 % des élèves** — une trentaine d'enfants, autant
de familles à prévenir, deux chauffeurs qui découvrent une nouvelle liste. Pour **une inscription**.

**La règle robuste se stabilise** : à partir de n = 284 elle tient `k = 7`, avec **0,7 à 1,0 %** de
churn — deux ou trois enfants, ceux que le nouvel arrivant concerne réellement.

**Mais son maximum est pire (25,4 %)**, et c'était un défaut de la proposition, pas de la mesure : à
n = 272, ⌈272/50⌉ = 6, donc six bus deviennent faisables et la règle de parcimonie saute dessus,
avant de revenir à sept. **La parcimonie court après tout `k` plus petit qui devient faisable.**

**D'où une troisième variante, une hystérésis** : ne changer de flotte que si l'ancien `k` est devenu
*infaisable*, ou si le nouveau le bat de plus de ε. Elle **domine les deux autres sur les trois
métriques** — churn moyen divisé par 3,2 et churn maximum par 1,7 par rapport à la règle actuelle,
avec seulement deux changements de flotte au lieu de neuf.

> C'est le seul des trois correctifs candidats qui n'ait **aucun contre-indicateur mesuré**.

**C. L'amorçage à chaud (warm start) — proposé, mesuré, puis retiré.** Initialiser les médoïdes sur
ceux du run précédent devait réduire le churn. À `k` fixé et ordre canonique, il est **légèrement
pire** : 0,7–2,7 % contre 0,0–1,7 % à froid. L'explication est claire *a posteriori* — quand l'ordre
est canonique et `k` stable, le K-Means à froid retombe déjà dans le même bassin, et l'amorçage
n'ajoute que de l'inertie. **Le churn ne vient pas de la dérive des médoïdes : il vient du changement
de `k`.** Recommandation abandonnée.

> Ce document ne corrige rien : il mesure et documente. Les correctifs recommandés sont au §7.

---

## 6. Les écarts de silhouette entre `k` voisins ont-ils un sens ?

Tout le service est figé à `random_state = 42`. Dix graines, k-médoïdes routier :

| k | Silhouette moyenne | Écart-type | Min | Max |
|--:|--:|--:|--:|--:|
| 6 | 0,3511 | 0,0001 | 0,3510 | 0,3513 |
| **7** | **0,4257** | **0,0001** | 0,4256 | 0,4258 |
| 8 | 0,4088 | 0,0119 | 0,3958 | 0,4433 |
| 9 | 0,4169 | 0,0204 | 0,3906 | 0,4599 |

- **k = 7 est remarquablement stable** (±0,0001) et domine k = 8 et k = 9 **en médiane** : le choix
  gelé est bien fondé.
- En revanche **k = 8 et k = 9 sont instables** (±0,012 et ±0,020) : leurs 0,006 d'écart, présentés
  comme des différences dans le dossier, sont **du bruit d'initialisation**.
- **C'est ce tableau qui explique le §5** : `choisir_k` fait un argmax sur ces valeurs, donc il
  départage des candidats indiscernables. Un `k` instable qui tire haut évince un `k` stable qui
  vaut mieux en moyenne. La sensibilité à l'ordre n'est que la manifestation visible de ce défaut.

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
- **Et une affirmation de ce document était fausse** : « le pipeline produit k=8 » (§5, v1). Le
  service produit **k=7**. Le benchmark exécutait la bonne fonction avec le mauvais ordre d'entrée.

**À corriger (décision de production, par ordre de priorité)**
1. **`choisir_k` fait un argmax sur du bruit** — c'est la cause racine, pas l'ordre. Médiane de la
   silhouette sur plusieurs initialisations par `k`, puis **plus petit `k`** à moins de ε ≈ 0,02 du
   meilleur. **Mesuré : k = 7 sur 15 permutations sur 15**, et le churn médian par inscription passe
   de **6,42 % à 1,03 %**. La sortie reste celle que le service produit déjà : le correctif
   **stabilise sans changer le comportement**.
2. **Ajouter une hystérésis sur `k`** : ne changer de flotte que si l'ancien `k` est devenu
   **infaisable**, ou si le nouveau le bat de plus de ε. Sans elle, la règle de parcimonie bascule
   dès qu'un `k` plus petit devient faisable — ce qui a produit le pic de churn à 25,4 % mesuré au
   franchissement de ⌈n/50⌉. **Combinée au point 1, c'est la variante qui domine sur les trois
   métriques** : churn moyen **2,25 %** contre 7,24 %, maximum **8,03 %** contre 13,27 %, et deux
   changements de flotte au lieu de neuf. Les deux points se font ensemble, pas l'un sans l'autre.
3. **Canoniser l'ordre d'entrée** dans `production_clustering` (côté MS6, pas seulement un
   `ORDER BY id` dans MS2) : l'invariant appartient au consommateur sensible à l'ordre.
   ⚠️ **Seul, ce correctif figerait `k = 8`** — l'ordre trié par id tombe précisément sur le `k` le
   moins fréquent (7 % des tirages). À faire **après** le point 1, jamais à sa place.
4. **Publier le churn comme métrique de production** (% d'élèves changeant de bus entre deux
   recalculs). C'est ce que les familles subissent, et ce n'était mesuré nulle part.
   *(L'amorçage à chaud, envisagé pour cela, a été mesuré puis abandonné — voir §5.)*
5. Réconcilier `production_config.json` (silhouette du **cœur**, 0,4334) avec ce que publie le
   service (silhouette **finale**, ≈ 0,405) et recalibrer la référence de `quality.py` : les deux
   grandeurs sont correctes, mais elles ne sont pas comparables entre elles.
6. ~~Supprimer ou archiver `model_metadata.json` et `benchmark_summary.json`, périmés et
   contradictoires.~~ ✅ **Fait le 29/08.** Renommés en `*.perime-v2-k6.bak`, selon la convention
   déjà utilisée pour `quality_baseline.json.perimee-17-07.bak`. Vérifié au préalable : **aucun
   code Python ne les lit**. Ils annonçaient `"choix_production": "K-Means capacitaire"` et
   `k = 6`, là où le service tourne en **k-médoïdes capacitaire routier à k = 7** — un lecteur du
   dépôt pouvait légitimement croire que le modèle de production était l'autre.

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

> ⚠️ **`ablation_distance.py` alimente le pipeline depuis le CSV trié par id, pas depuis MS2.**
> C'est ce qui a produit l'erreur du §5. Les comparaisons **à `k` fixé** (l'arène du §3, l'ablation
> du §4) restent valides : tous les concurrents y subissent le même ordre, ce qui est précisément la
> règle du protocole. Seule la ligne « pipeline complet », qui laisse le pipeline **choisir** `k`,
> était affectée — et elle a été remplacée par la mesure de sensibilité à l'ordre.

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
