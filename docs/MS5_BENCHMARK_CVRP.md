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

Sur les **300 élèves** et les **7 groupes réels** produits par MS6, en faisant grandir l'instance :

| Groupes | Élèves | MS6 + TSP | CVRP global | Écart |
|--:|--:|--:|--:|:--|
| 2 | 79 | 59,4 min | 59,2 min | +0,2 % CVRP |
| 3 | 129 | 74,3 min | 76,0 min | **−2,3 % MS6** |
| 4 | 165 | 100,2 min | 100,9 min | −0,7 % MS6 |
| 5 | 215 | 135,8 min | 137,7 min | −1,4 % MS6 |
| 6 | 257 | 164,1 min | 163,9 min | +0,1 % CVRP |
| 7 | **300** | **207,1 min** | **208,0 min** | **−0,4 % MS6** |

![Comparaison](../ms5-planification/notebooks/figures/06_cvrp_vs_ms6_tsp.png)

**À budget égal, le CVRP ne bat jamais la décomposition de plus de 0,2 %** — et il lui est le plus
souvent inférieur, jusqu'à −2,3 %.

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

![Charges](../ms5-planification/notebooks/figures/06_equilibrage_charges.png)

| | Bus utilisés | Charge min | Charge max | Écart-type |
|---|--:|--:|--:|--:|
| MS6 + TSP | 7 | 29 | 50 | **7,49** |
| CVRP global | **6** | 50 | 50 | **0,00** |

> **Un bus — donc un chauffeur — économisé, pour +0,4 % de temps de conduite.**

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

**« +0,4 %, ce n'est pas dans le bruit de mesure ? »**
Si, et c'est bien ce qu'on affirme : les deux approches sont **équivalentes en distance**. La
conclusion ne repose pas sur ce 0,4 % — elle repose sur le fait que le CVRP **n'apporte rien** là où
on l'attendait, tout en révélant un gain ailleurs (le nombre de bus).

**« Votre TSP est-il déterministe ? »**
Non, et le notebook le dit. `GUIDED_LOCAL_SEARCH` est borné **en temps**, pas en itérations : deux
exécutions sur une machine plus ou moins chargée explorent différemment. Le contrôle de cohérence
retrouve la référence de production à **−3,1 %** en distance — du bruit de solveur, pas une dérive.
Un écart de 20 % aurait signalé un vrai problème.

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
python notebooks/build_notebooks.py           # (re)génère le notebook
python -m jupyter nbconvert --execute --to notebook --inplace \
    --ExecutePreprocessor.timeout=3600 notebooks/06_cvrp_benchmark.ipynb
```

Figures produites dans `ms5-planification/notebooks/figures/06_*.png`.

> Les chiffres exacts varieront de quelques pour cent d'une exécution à l'autre — heuristique bornée
> en temps. Les **conclusions**, elles, sont stables : pas d'écart significatif en durée, et un bus
> économisé par le CVRP.
