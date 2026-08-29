# Benchmark CVRP global vs MS6 + TSP

> **Document pédagogique.** Il explique une question d'optimisation, comment on l'a tranchée par la
> mesure, et pourquoi le résultat n'est pas celui qu'on attendait. Aucune connaissance préalable en
> recherche opérationnelle n'est supposée.
>
> Code : [`ms5-planification/cvrp.py`](../ms5-planification/cvrp.py) ·
> Notebook : [`06_cvrp_benchmark.ipynb`](../ms5-planification/notebooks/06_cvrp_benchmark.ipynb)

---

## 1. La question, en une phrase

Le système résout le transport scolaire **en deux temps** :

1. **MS6** décide *quel élève monte dans quel bus* (sous contrainte de 50 places) ;
2. **MS5** décide *dans quel ordre* chaque bus passe prendre ses élèves.

C'est une **décomposition**. Or il existe une formulation qui résout les deux décisions **d'un seul
bloc** : le **CVRP**. Et en théorie, décider tout ensemble ne peut qu'être meilleur ou égal que
décider en deux fois.

> **Alors, combien nous coûte le fait d'avoir découpé le problème ?**

C'était la dernière promesse de comparaison encore ouverte dans la documentation du projet. La voici
tenue.

---

## 2. Les deux façons de poser le problème

### TSP — « le voyageur de commerce »

Un bus, une liste d'arrêts, une question : **dans quel ordre les visiter pour rentrer le plus vite ?**
Le bus part de l'école, passe partout, revient à l'école. C'est ce que fait
[`vrp.py`](../ms5-planification/vrp.py) aujourd'hui, **une fois par bus**.

Le TSP ne choisit **pas** qui monte dans quel bus : cette décision lui est donnée toute faite par MS6.

### CVRP — « tournées de véhicules avec capacité »

*Capacitated Vehicle Routing Problem.* Une flotte, un dépôt, tous les élèves, et **deux** questions
simultanées : **qui va dans quel bus** *et* **dans quel ordre**. La contrainte de capacité (50 places)
fait partie du modèle.

Le CVRP a donc **plus de liberté** que la chaîne MS6 → TSP : il peut déplacer un élève d'un bus à un
autre si ça raccourcit l'ensemble. C'est précisément ce qu'on veut mesurer.

### Pourquoi on n'a pas fait ça dès le départ

Parce que la liberté a un prix : l'espace de recherche du CVRP est **beaucoup** plus grand
(affectation × routage), et il ne se découpe pas. Sept TSP de cinquante arrêts se résolvent
indépendamment — et donc **en parallèle**, ce que fait déjà `/tournees` avec `asyncio.gather`
(43 s → 9 s mesuré). Un CVRP de trois cents arrêts est un seul gros calcul, insécable.

---

## 3. Ce qui rend une comparaison honnête

C'est la partie la plus importante du travail, et la plus facile à bâcler. **Cinq règles**, sans
lesquelles le résultat ne voudrait rien dire :

| Règle | Ce qu'on éviterait sinon |
|---|---|
| **Une seule matrice de distances**, construite une fois ; l'approche A y prend des sous-matrices par simple indexation | Comparer deux solveurs sur deux jeux de distances différents |
| **Même grandeur minimisée** : la durée en secondes | Un solveur qui minimise les kilomètres bat forcément l'autre… sur les kilomètres |
| **Même arrondi entier** de la matrice | OR-Tools travaille en entiers ; deux arrondis différents = deux problèmes différents |
| **Budget de calcul égalisé** : A = 7 TSP × 5 s ; B = **une** résolution de 7 × 5 s = 35 s | Donner plus de temps de réflexion à l'un des deux |
| **Même flotte** : même nombre de bus, même capacité | Le CVRP « gagnerait » en ajoutant des véhicules |

Le budget égalisé mérite un mot : l'approche A dispose de 5 secondes **par bus**, donc 35 secondes de
calcul au total sur sept groupes. On donne donc au CVRP ces mêmes 35 secondes pour son unique
résolution. C'est le seul découpage équitable.

---

## 4. Deux obstacles rencontrés — et pourquoi ils comptent

### OSRM refuse au-delà de 100 coordonnées… **en silence**

Le service de matrice d'OSRM (`/table`) plafonne à 100 coordonnées par requête. Au-delà, il renvoie
`400 Bad Request`. Or [`osrm_client.py`](../ms5-planification/osrm_client.py) de MS5 fait **un seul
appel** — ce qui lui suffit largement en production, où une tournée compte au plus une cinquantaine
d'arrêts, mais qui casse ici dès trois groupes.

Le vrai piège n'est pas l'erreur : c'est que MS5 **retombe alors sur une distance à vol d'oiseau**
sans rien signaler d'autre qu'une ligne de log. La première exécution du benchmark n'a donc comparé
que 2 groupes, et sur une matrice qui n'avait plus rien de routier.

**Correctif** : on reprend le mécanisme de MS6 — la matrice est assemblée **par blocs de 50 × 50**,
chaque requête n'envoyant que l'union de deux blocs (≤ 100 coordonnées) avec des index
`sources`/`destinations` locaux. Les 301 points passent alors sans difficulté.

### On ne symétrise pas

MS6 termine sa matrice par `D = (D + Dᵀ) / 2` : il lui faut une *distance* au sens mathématique pour
ses k-médoïdes. Ici, on s'en garde bien. Aller de A vers B ne coûte pas la même chose que B vers A —
sens uniques, tourne-à-gauche interdits — et **cette asymétrie est exactement ce qui fait le coût
réel d'une tournée**. C'est déjà l'argument de `verify_sens.py` sur le choix « soir = même ordre que
le matin ». La lisser fausserait les deux approches à la fois.

*Contrôle effectué :* sur les 361 paires testées, **328 sont asymétriques** — la matrice est bien du
routier réel, pas un repli déguisé.

---

## 5. Les résultats

> ⚠️ **Chiffres remis à jour le 29/08.** La campagne d'origine (23/08) avait tourné sur la
> partition d'alors, `50·50·50·43·42·36·29`. La **migration vers k = 7 du 27/08** en a produit une
> autre — `50·50·48·44·42·37·29`, mêmes sept bus et trois cents élèves, mais pas les mêmes élèves
> dans les mêmes bus. Le benchmark décrivait donc un système qui n'existait plus.
> Il a été **rejoué sur la partition en vigueur** ([`rejouer_cvrp.py`](../ms5-planification/rejouer_cvrp.py),
> élèves lus en direct depuis MS2). C'est la **règle 7** du protocole appliquée à un benchmark qui
> avait vieilli. Les chiffres ci-dessous sont ceux du rejeu ; la comparaison des deux campagnes
> est au §5 bis.

Sur les **300 élèves** et les **7 groupes réels** produits par MS6, en faisant grandir l'instance :

| Groupes | Élèves | MS6 + TSP | CVRP global | Écart |
|--:|--:|--:|--:|:--|
| 2 | 94 | 61,8 min | 61,5 min | +0,4 % CVRP |
| 3 | 136 | 90,0 min | 90,0 min | 0,0 % |
| 4 | 173 | 133,1 min | 133,4 min | −0,2 % MS6 |
| 5 | 223 | 148,0 min | 153,4 min | **−3,7 % MS6** |
| 6 | 271 | 182,7 min | 180,9 min | +0,9 % CVRP |
| 7 | **300** | **206,8 min** | **208,0 min** | **−0,6 % MS6** |

![Comparaison](../ms5-planification/notebooks/figures/05_1_ecart_vs_taille.png)

**À budget égal, le CVRP ne gagne au mieux que 0,9 %** — et il est le plus souvent inférieur,
jusqu'à −3,7 %.

### 5 bis. La réplication : la conclusion résiste au changement de partition

| Groupes | Écart 23/08 *(ancienne partition)* | Écart 29/08 *(partition actuelle)* |
|--:|--:|--:|
| 2 | +0,2 % | +0,4 % |
| 3 | −2,3 % | 0,0 % |
| 4 | −0,7 % | −0,2 % |
| 5 | −1,4 % | −3,7 % |
| 6 | +0,1 % | +0,9 % |
| 7 | −0,4 % | −0,6 % |

![Réplication](../ms5-planification/notebooks/figures/05_4_replication.png)

Les écarts point par point bougent — c'est attendu, ce sont d'autres instances. **Les deux
résultats structurels, eux, sont identiques** : le CVRP se passe toujours du 7ᵉ bus, en remplissant
à 50/50 exactement (écart-type 0,00). *Une conclusion qui survit à un changement de données est
plus solide qu'une conclusion obtenue une seule fois.*

### 5 ter. Correction : le TSP **est** déterministe

La version initiale de ce document affirmait un bruit de solveur d'« environ 3 % », déduit d'un
écart de −3,1 % entre le banc d'essai et la référence de production. **C'était une erreur
d'interprétation** : cet écart ne venait pas du solveur, mais du fait que les deux tournées
comparées portaient sur **deux groupes d'élèves différents** (celui d'avant migration contre celui
d'après).

Mesuré correctement — la **même** instance résolue plusieurs fois :

| Instance | Budget | Répétitions | Étendue |
|---|--:|--:|--:|
| TSP, un bus, 50 arrêts | 5 s | 5 | **0,00 %** |
| CVRP, 7 bus, 300 arrêts | 35 s | 3 | **0,00 %** |

Dans un même processus, les deux solveurs sont **reproductibles**. La variation apparaît **entre
exécutions séparées** : le CVRP à 6 groupes a donné 180,9 puis 179,9 min lors de deux lancements
successifs, soit **0,55 %**. C'est l'ordre de grandeur du bruit à retenir — et il reste inférieur
aux écarts de 3,7 % observés en faveur de la décomposition.

*(Ce résultat rejoint celui déjà noté dans [MS6](MS6_BENCHMARK_DISTANCE.md) §8 : « le TSP aval s'est
révélé parfaitement déterministe sur ces instances ».)*

Ce n'est pas le résultat attendu. La théorie dit qu'un CVRP résolu **à l'optimum** est au moins aussi
bon. Mais on ne résout pas à l'optimum : on donne 35 secondes à une heuristique. Et en 35 secondes,
sur trois cents arrêts, elle ne retrouve pas ce que MS6 savait déjà.

---

## 6. Pourquoi la décomposition tient — et c'est le point à retenir

> **Les k-médoïdes de MS6 travaillent déjà sur la distance routière OSRM.**

Ce n'est pas un détail d'implémentation, c'est *toute* l'explication. MS6 ne découpe pas la carte au
hasard ni sur des coordonnées brutes : il regroupe les élèves selon le **temps de route réel** qui les
sépare. L'information géographique est donc injectée dans le problème **avant** le routage.

Le CVRP, lui, part à froid. Il doit redécouvrir cette structure tout seul, sur un espace de recherche
bien plus vaste, et dans le même temps de calcul.

**La décomposition n'est donc pas une approximation qu'on subit : c'est une façon d'injecter de la
connaissance du domaine dans le solveur.** C'est un résultat classique en recherche opérationnelle,
mais il est ici *mesuré* sur les données du projet, pas récité.

---

## 7. Le résultat inattendu : un bus de moins

Le tableau des durées cache la découverte la plus intéressante. Avec **7 bus disponibles**, le CVRP
n'en utilise que **6** — chargés à **50 / 50 exactement**.

![Charges](../ms5-planification/notebooks/figures/05_2_equilibrage_flotte.png)

| | Bus utilisés | Charge min | Charge max | Écart-type |
|---|--:|--:|--:|--:|
| MS6 + TSP | 7 | 29 | 50 | **7,14** |
| CVRP global | **6** | 50 | 50 | **0,00** |

> **Un bus — donc un chauffeur — économisé, pour +0,6 % de temps de conduite.**

*(Ce résultat est le plus robuste du benchmark : il est **identique** dans les deux campagnes, sur
deux partitions différentes — voir §5 bis.)*

### Ce n'est pas une erreur de MS6, c'est un arbitrage différent

Le minimum théorique est ⌈300 / 50⌉ = **6 bus**. MS6 en choisit **7**, et il le fait exprès : sa
courbe de Pareto arbitre entre le nombre de bus et la **compacité géographique** des groupes. Ce
septième bus achète deux choses que la colonne « durée » ne montre pas :

1. **Des tournées plus compactes** — donc moins de temps passé à bord pour chaque enfant, ce que le
   projet cherche justement à réduire. La durée totale de la flotte n'est pas la seule métrique qui
   compte pour une famille.
2. **De la marge.** La solution du CVRP à six bus pleins n'en a **aucune** : un élève de plus, et
   l'instance devient infaisable. Or une inscription en cours d'année est le cas normal dans une
   école — pas une exception.

C'est exactement le genre d'arbitrage qu'un chiffre unique masque, et qu'un benchmark bien construit
révèle.

---

## 8. Verdict

**On garde MS6 + TSP.** Trois raisons, toutes mesurées :

- **aucun surcoût en conduite** — le CVRP ne fait pas mieux à budget égal ;
- **parallélisable** — sept TSP indépendants, contre un bloc insécable (43 s → 9 s en production) ;
- **de la marge de capacité** — la solution reste viable quand un élève s'inscrit en cours d'année.

**Et le CVRP n'est pas jeté** : il devient un **outil de dimensionnement de flotte**. C'est lui qui
répond à « combien de bus me faut-il *au minimum* ? », question à laquelle MS6 ne répond pas puisqu'il
optimise la compacité. Une piste immédiate : le relancer avec un `cout_fixe_vehicule` élevé pour
tracer le compromis *flotte minimale ↔ temps à bord*.

---

## 9. Questions que le jury peut poser

**« Pourquoi ne pas simplement laisser tourner le CVRP plus longtemps ? »**
On pourrait, et il finirait par rattraper puis dépasser. Mais la comparaison porte sur un usage
**opérationnel** : la tournée se recalcule quand un élève déménage ou qu'un bus tombe en panne. À
budget de calcul réaliste, la décomposition gagne. Et si l'on décide d'allouer plus de temps,
l'approche A en profite aussi — ses sept TSP tournent en parallèle.

**« +0,6 %, ce n'est pas dans le bruit de mesure ? »**
Si, et c'est bien ce qu'on affirme : sur ce point les deux approches sont **équivalentes**. La
conclusion ne repose pas sur ce 0,6 % — elle repose sur le fait que le CVRP **n'apporte rien** là où
on l'attendait, tout en révélant un gain ailleurs (le nombre de bus). Le bruit inter-exécutions a
d'ailleurs été mesuré : **0,55 %** (§5 ter). L'écart de **3,7 %** en faveur de la décomposition à
5 groupes, lui, le dépasse nettement.

**« Votre TSP est-il déterministe ? »**
**Oui, et c'est mesuré** — 5 exécutions de la même instance, étendue **0,00 %** (§5 ter). Le CVRP
l'est aussi dans un même processus. Une variation n'apparaît qu'**entre exécutions séparées**, et
elle vaut **0,55 %**.

> ⚠️ **Ce document affirmait le contraire avant le 29/08** — « environ 3 % de bruit de solveur ».
> Ce chiffre venait d'un contrôle qui comparait deux tournées portant sur **deux groupes d'élèves
> différents** : ce n'était pas du bruit, c'était une autre instance. Le corriger était nécessaire,
> parce qu'un bruit surestimé aurait servi à écarter des écarts réels.

**« Pourquoi ne pas avoir comparé sur toute la flotte d'un coup, sans faire varier la taille ? »**
Parce que la question intéressante n'est pas « qui gagne sur 300 élèves », c'est « **l'écart
grandit-il avec la taille ?** » — c'est-à-dire : la décomposition se dégrade-t-elle quand le problème
grossit ? La réponse est non, et il fallait six points de mesure pour le dire.

---

## 10. Reproduire

Pré-requis : **MS2** (`:8082`) pour les groupes réels, **OSRM** (`:5000`) pour la matrice.

```bash
docker-compose up -d && docker start osrm_meknes
cd ms2-eleves && mvn spring-boot:run          # dans son propre terminal

cd ms5-planification
python rejouer_cvrp.py                        # ~6 min → data/cvrp_benchmark_resultats.json
python notebooks/gen_figures_memoire.py       # figures, hors ligne
```

Le calcul et le tracé sont **séparés** : `rejouer_cvrp.py` exige MS2 et OSRM, mais
`gen_figures_memoire.py` ne lit que le JSON. Deux avantages — on retrace les figures sans rallumer
la stack, et **toutes les figures d'un rapport décrivent la même exécution**, ce qui ne serait pas
garanti si chacune relançait un solveur borné en temps.

Figures produites dans `ms5-planification/notebooks/figures/05_*.png` (et `.pdf`).

> **À refaire après toute migration de partition MS6.** C'est précisément ce qui a rendu la
> campagne du 23/08 caduque, et le rejeu du 29/08 nécessaire.

*(L'ancien chemin — `build_notebooks.py` puis `nbconvert --execute` — reste possible, mais il
réexécute le notebook entier et **efface ses sorties stockées**, dont les figures du mémoire qui y
sont embarquées.)*
