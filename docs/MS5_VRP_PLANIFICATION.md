# 📙 MS5 — Optimisation des tournées de bus (VRP)
### Documentation simple — comment ça marche, avec figures expliquées
*Transport Scolaire Intelligent — PFE SDIA · Meknès · Sprint S10*

---

## 1. À quoi sert MS5 ? (en une phrase)

Une fois que **MS6 a réparti les élèves dans les bus** (par capacité), MS5 décide **dans quel ORDRE** chaque
bus doit passer prendre ses élèves pour **rouler le moins longtemps possible**.

> **Analogie :** MS6 dit *« ces 40 élèves montent dans le bus 3 »*. MS5 dit *« voici le meilleur itinéraire :
> école → élève C → élève A → … → école, 31 min au lieu de 39 »*.

**Complémentarité :** MS6 = *qui va dans quel bus* · MS5 = *dans quel ordre* (le temps de tournée).

---

## 2. Comment ça marche ? (le principe)

Pour **un bus**, c'est le problème classique du **voyageur de commerce (TSP)** :
- **Dépôt = l'école** 🏫 : le bus part de l'école, ramasse tous ses élèves, revient à l'école.
- **Coût d'un trajet** = la **durée routière réelle** entre deux points (fournie par **OSRM**, le moteur de
  routage sur le réseau OSM de Meknès).
- **OR-Tools** (solveur d'optimisation de Google) cherche **l'ordre de passage** qui minimise la durée totale.
- On compare au résultat d'une méthode naïve (**« plus proche voisin »**) pour mesurer le **gain**.

**Pipeline :**
```
MS6 (groupes) → MS2 (groupeId) → MS5 : pour chaque bus
   arrêts (école + élèves) → matrice de durées OSRM → OR-Tools (TSP) → ordre optimal + carte + gain
```

---

## 2bis. Le problème du voyageur de commerce (TSP) — en détail

### a) L'énoncé (simple)
> Un bus doit partir de l'**école**, passer **une seule fois** par chaque arrêt-élève, puis **revenir à
> l'école**, en **parcourant le moins de temps possible**. Dans quel **ordre** visiter les arrêts ?

C'est le **TSP** (*Travelling Salesman Problem*) : trouver le **circuit le plus court** qui visite tous les
points et revient au départ. Le point de départ/retour s'appelle le **dépôt** (ici : l'école 🏫).

### b) Pourquoi c'est difficile : l'explosion combinatoire
On pourrait croire qu'il suffit de « tester tous les ordres ». Mais le nombre d'ordres possibles **explose** :
pour *n* arrêts, il y a **(n−1)! / 2** circuits distincts.

| Arrêts | Nombre d'ordres à tester |
|---|---|
| 5 | 12 |
| 10 | 181 440 |
| 15 | ~43 **milliards** |
| 20 | ~60 **millions de milliards** |
| 50 (un bus plein) | plus que d'atomes observables… |

→ **Impossible** de tout énumérer. C'est un problème dit **NP-difficile** : pas de méthode connue qui donne la
solution exacte rapidement quand *n* grandit. On utilise donc des **heuristiques** (des méthodes malines qui
trouvent une **très bonne** solution en quelques secondes, sans garantir l'optimum absolu).

### c) Notre modélisation
- **Nœuds** : l'école (dépôt) + les arrêts-élèves du bus.
- **Coût d'un arc** i→j : la **durée routière réelle** (OSRM), pas la ligne droite. La matrice peut même être
  **asymétrique** (sens interdits, sens uniques → aller ≠ retour), ce que le TSP gère.
- **Objectif** : minimiser la **somme des durées** du circuit complet (école → … → école).

### d) Comment OR-Tools le résout (en 2 temps)
OR-Tools ne teste pas tous les ordres. Il procède comme un humain malin :

**1. Une première solution rapide (construction) — `PATH_CHEAPEST_ARC`**
Part du dépôt et va à chaque fois vers l'arrêt **le plus proche non encore visité** (c'est notre *baseline*
« plus proche voisin »). Rapide, mais **imparfait** : ça crée souvent des **allers-retours** et des
**croisements** (le bus se coupe lui-même).

**2. L'amélioration (recherche locale) — `GUIDED_LOCAL_SEARCH` + 2-opt / Or-opt**
On **améliore** la solution par petits gestes répétés, sous un **budget de temps** :
- **2-opt** : on prend deux tronçons qui se **croisent** et on les **inverse** → on **décroise** l'itinéraire
  (deux lignes qui se coupent sont toujours plus longues que si on les décroise).
- **Or-opt** : on **déplace** un arrêt (ou une petite séquence) à un meilleur endroit du circuit.
- **Guided Local Search** : quand on est coincé dans un « optimum local » (on ne peut plus améliorer par un
  petit geste), la méthode **pénalise** temporairement les arcs suspects pour **forcer** l'exploration
  d'autres routes → elle **s'échappe** des pièges et continue de progresser.

```
   Étape 1 (plus proche voisin)        Étape 2 (2-opt : on décroise)
        A───────B                           A───────B
         \     /                            │       │
          \   /       ✂ croisement  →       │       │      = plus court
           \ /                              │       │
        D───X───C                           D───────C
```

### e) Le résultat
En **quelques secondes**, OR-Tools rend une tournée **quasi-optimale** — souvent bien meilleure que le
« plus proche voisin ». **C'est exactement ce que montre la figure 4.1** : à gauche (baseline) les lignes se
**croisent** (allers-retours) ; à droite (optimisé) le circuit est **décroisé** et plus court → d'où le gain %.

> **Résumé :** le TSP = trouver le meilleur ordre de visite ; c'est trop dur pour tout énumérer, donc OR-Tools
> construit une solution rapide puis la **décroise/améliore** jusqu'à une tournée quasi-optimale, en utilisant
> les **vraies durées OSRM**.

---

## 3. ✅ Vérification : ce sont de VRAIES routes (pas des lignes droites)

Question légitime : est-ce qu'on utilise le **vrai réseau routier** ou juste des distances « à vol d'oiseau » ?
**Preuve mesurée** (école + 3 arrêts de Meknès) :

| Trajet | Distance **routière** (OSRM) | Distance **à vol d'oiseau** | Ratio |
|---|---|---|---|
| école → Médina | 3 493 m | 851 m | **4.10×** |
| école → Wislane | 2 846 m | 1 523 m | 1.87× |
| Médina → Wislane | 2 295 m | 1 691 m | 1.36× |

- La route est **toujours plus longue** que la ligne droite (1.14× à **4.10×**) — normal : le bus **contourne**
  (oued, sens de circulation, rues réelles).
- La **géométrie** d'une tournée contient **521 points** (pas seulement les 4 arrêts) → elle **épouse les rues**.
- OSRM répond `code: Ok`. **Verdict : vraies routes OSRM.** *(Repli à vol d'oiseau uniquement si OSRM est éteint.)*

---

## 4. Les figures (notebook `05_vrp_study.ipynb`) expliquées

### 4.1 Baseline vs Optimisé — la même tournée, deux ordres
On prend le bus au **plus fort gain** (le plus parlant). À gauche l'ordre **naïf** (« va toujours au plus
proche »), à droite l'ordre **optimisé** par OR-Tools. Les lignes relient les arrêts **dans l'ordre de visite** ;
🏫 = école (départ/arrivée).

![Baseline vs optimisé](../ms5-planification/notebooks/figures/05_baseline_vs_optimise.png)

**Comment lire :** l'ordre naïf fait des **allers-retours** inutiles (lignes qui se croisent) ; l'ordre optimisé
est plus « fluide » et **plus court** (voir la durée dans les titres). Le gain de temps est le % affiché.

### 4.2 La tournée optimale sur le vrai réseau routier
Ici on trace l'itinéraire réel (géométrie OSRM) du bus, avec l'**ordre de passage numéroté** (1, 2, 3…) et
l'école (⭐).

![Tournée réelle OSRM](../ms5-planification/notebooks/figures/05_tournee_reelle.png)

**Comment lire :** la ligne bleue **suit les rues** (ce n'est pas une ligne droite entre les points). Les
numéros donnent l'ordre dans lequel le chauffeur ramasse les élèves.

### 4.3 Le gain sur toute la flotte
Pour chaque bus, le **gain** (temps économisé vs l'ordre naïf).

![Gain par bus](../ms5-planification/notebooks/figures/05_gains_flotte.png)

**Comment lire :** le gain **dépend de la forme du groupe** — un petit groupe compact peut déjà être optimal
(**gain 0 %**, bus 1), un groupe grand/étalé gagne beaucoup (**~21 %**, bus 3). La ligne pointillée = **moyenne**.

---

## 5. Résultats (données v2, 9 bus)

| Indicateur | Valeur |
|---|---|
| Nombre de bus | 9 |
| Distance totale | ~107.9 km |
| Durée totale | ~224 min |
| **Gain moyen vs ordre naïf** | **~12.6 %** |
| Meilleur bus | bus 3 : **21.4 %** (39.4 → 31.0 min) |

> **Honnêteté :** le gain est **variable** (0 % à 21 %) selon la géométrie du groupe. C'est un résultat
> **réaliste** : sur les petits groupes compacts, le simple bon sens suffit ; c'est sur les grands groupes
> étalés que l'optimisation apporte le plus.

---

## 6. Comment l'utiliser (API)

Sécurité : **JWT** (ADMIN/CHAUFFEUR). Route Gateway `ms5-planification` (8085) déjà en place.

| Route | Description |
|---|---|
| `GET /api/planification/health` | statut + solveur |
| `POST /api/planification/tournee?groupeId=&sens=matin\|soir` | tournée d'un bus → `{ ordre, etapes, distance_m, duree_min, gain_vs_baseline_%, geometrie }` |
| `POST /api/planification/tournees?sens=` | toutes les tournées + totaux + gain moyen |
| `POST /api/planification/mes-enfants?sens=` | **rôle PARENT** — étapes des SEULS enfants du demandeur (rang + cumul depuis l'école). Portée prise dans le **JWT**, jamais dans la requête |

`etapes` donne, pour chaque élève, son `rang` et le **cumul depuis l'école** (`cumul_distance_m`,
`cumul_duree_s`) : c'est ce qui permet de dater l'arrivée d'un élève précis (« votre enfant est pris vers 7 h 42 »)
et c'est l'entrée que les écrans « Prévisions » passent à MS12.

> **Pourquoi un endpoint dédié au parent** : `/tournee` expose l'ordre **et les domiciles de toutes les familles**
> du bus. L'ouvrir au rôle PARENT serait une fuite. MS5 calcule donc la tournée complète — indispensable au cumul —
> puis filtre sur le `parentId` du jeton avant de répondre.

`sens=matin` = ramassage (école→arrêts→école) ; `sens=soir` = dépose sur la **même** tournée (**même ordre**, pas
l'inverse). Pourquoi : « même ordre » et « ordre inversé » parcourent le même cycle, mais garder le même ordre
**équilibre le temps à bord** sur la journée (matin + soir ≈ une durée de tournée pour chaque élève), alors que
l'inverser pénalise deux fois l'élève ramassé en premier. De plus, sur les routes OSRM réelles (**asymétriques**),
l'ordre inversé n'est pas ré-optimisé et coûte souvent plus cher. Preuve chiffrée : `ms5-planification/verify_sens.py`.

**Démo (console `test-console.html`)** : onglet 🗺️ **Tournées** → *Calculer & tracer* → les bus s'affichent en
couleurs sur la carte, chaque tracé suivant les vraies routes.

---

## 7. Reproduire

```bash
conda activate nlp           # ortools installé
docker start osrm_meknes     # OSRM (sinon repli vol d'oiseau)
# 1) clustering appliqué (groupes en base) :
#    POST /api/clustering/production?appliquer=true
# 2) service VRP :
cd ms5-planification ; uvicorn main:app --port 8085
# 3) notebook :
python notebooks/build_notebooks.py
jupyter nbconvert --to notebook --execute --inplace notebooks/05_vrp_study.ipynb
```

---

## 8. Fichiers & architecture

```
ms5-planification/            (port 8085, /api/planification/**)
├── main.py         ← FastAPI + JWT : health / tournee / tournees
├── config.py       ← port, jwt_secret, ms2_url, osrm_url, école (dépôt)
├── ms2_client.py   ← élèves par groupe (filtrés depuis /api/eleves)
├── osrm_client.py  ← matrice durées/distances (/table) + géométrie (/route GeoJSON, continue_straight=false)
├── vrp.py          ← OR-Tools TSP (dépôt=école) + baseline plus-proche-voisin
├── planner.py      ← orchestrateur : groupe → matrice → solve → ordre + gain + géométrie
├── notebooks/05_vrp_study.ipynb + figures/
└── requirements.txt · Dockerfile · .env
```
**Réutilise** : les groupes **réels de MS6** (via MS2), le pattern OSRM, le JWT MS7. **Gateway** : route déjà réservée.

## 8 bis. `continue_straight=false` — pourquoi la géométrie et la distance divergeaient de 11 %

MS5 produit **deux** grandeurs qui décrivent censément le même trajet : `distance_m`, somme des arcs de la
matrice OSRM `/table` (l'objectif que le TSP minimise), et `geometrie`, la polyligne renvoyée par `/route`.
Elles ne coïncidaient pas.

Par défaut, OSRM impose au véhicule de **poursuivre tout droit en franchissant chaque waypoint**
(`continue_straight=default`). Quand l'arrêt suivant est en arrière, il insère donc un **demi-tour** au lieu de
tourner. Sur 50 arrêts, l'effet s'accumule. Mesuré contre l'OSRM local sur les 52 waypoints réels du groupe 1 :

| Appel | Distance | Durée | Points |
|---|---:|---:|---:|
| `/route` **sans** `continue_straight` | 19 123,5 m | 42,23 min | 882 |
| `/route` **avec** `continue_straight=false` | **17 241,1 m** | **35,99 min** | 753 |
| Matrice `/table` (référence, `distance_m`) | 17 241,1 m | 35,99 min | — |

Soit **+10,92 % de trajet fantôme**, et une polyligne qui décrivait un **autre itinéraire** que celui optimisé.
Vérifié avec un haversine de référence que l'écart ne venait pas de la projection côté client (0,008 %).

**Deux conséquences en aval, toutes deux levées par le correctif :**

1. **ETA faussé.** Les clients mesurent les mètres restants **sur la polyligne** puis les convertissent avec une
   vitesse. S'ils déduisaient cette vitesse de `distance_m`, ils divisaient des mètres d'une géométrie par la
   vitesse d'une autre — l'ETA était gonflé d'autant. *(Les clients dérivent désormais la vitesse de la polyligne
   qu'ils mesurent : immunité si la divergence revenait.)*
2. **Référence de déviation MS11 polluée.** MS11 fige cette polyligne au démarrage du trajet et lève
   `DEVIATION_ITINERAIRE` quand le bus s'en écarte de plus de 250 m. Des demi-tours **que le bus ne fera jamais**
   sont autant de faux positifs en puissance.

Après correctif : convergence à **0,05 %**, et une déviation forcée déclenche toujours l'anomalie — la
surveillance n'a pas été désarmée par le changement de géométrie.

> ⚠️ La tournée reste un **cycle fermé** : le premier et le dernier point sont à 0,0 m l'un de l'autre. Les
> clients qui projettent une position dessus doivent mémoriser la progression déjà acquise, sans quoi un bus
> arrivé à l'école se recale sur le **départ**. Voir `route_eta.dart` / `routeEta.ts` et le piège 13 de
> `CLAUDE.md`.

## 8 ter. Benchmark : CVRP global vs MS6 + TSP (mesuré)

La décomposition MS6 → MS5 est *a priori* sous-optimale : l'affectation est figée **avant** de connaître le coût
des tournées qui en découlent. Combien coûte-t-elle ? Le notebook `notebooks/06_cvrp_benchmark.ipynb` compare
l'approche de production à un **CVRP global** (`cvrp.py`) qui résout affectation et routage d'un bloc.

**Protocole** — une seule matrice OSRM construite par blocs de 50×50 (le `/table` d'OSRM plafonne à 100
coordonnées ; l'approche A en extrait ses sous-matrices, elle ne refait aucun appel), même grandeur minimisée
(la durée), même arrondi entier, **même budget de calcul** (A = k TSP × 5 s ; B = une résolution de k × 5 s),
même nombre de bus et même capacité. Matrice **non symétrisée** : l'asymétrie du réseau est une information.

**Résultat sur les 300 élèves / 7 groupes réels :**

| Groupes | Élèves | MS6 + TSP | CVRP global | Écart |
|--:|--:|--:|--:|:--|
| 2 | 79 | 59,4 min | 59,2 min | +0,2 % CVRP |
| 3 | 129 | 74,3 min | 76,0 min | −2,3 % **MS6** |
| 4 | 165 | 100,2 min | 100,9 min | −0,7 % **MS6** |
| 5 | 215 | 135,8 min | 137,7 min | −1,4 % **MS6** |
| 6 | 257 | 164,1 min | 163,9 min | +0,1 % CVRP |
| 7 | **300** | **207,1 min** | **208,0 min** | **−0,4 % MS6** |

**À budget égal, le CVRP ne bat jamais la décomposition de plus de 0,2 %** et lui est le plus souvent
inférieur. Le résultat attendu — « résoudre les deux décisions ensemble doit faire mieux » — n'est pas au
rendez-vous, et l'explication est instructive : les k-médoïdes de MS6 travaillent **déjà sur la distance
routière OSRM**, donc l'information géographique est injectée *avant* le routage. Le CVRP doit la redécouvrir
seul, sur un espace de recherche bien plus vaste, dans le même temps. **La décomposition n'est pas une
approximation subie : c'est une façon d'injecter de la connaissance du domaine dans le solveur.**

**Mais le CVRP trouve autre chose.** Avec 7 véhicules disponibles, il n'en utilise que **6**, chargés à
**50/50 exactement** (écart-type des charges **0,00**), là où MS6 en utilise 7 chargés de 29 à 50
(écart-type 7,49) : **un bus — donc un chauffeur — économisé pour +0,4 % de temps de conduite.**

Ce n'est pas une erreur de MS6, c'est un arbitrage différent. Le minimum théorique est ⌈300/50⌉ = 6 bus ;
MS6 en prend 7 parce que sa courbe de Pareto privilégie la compacité géographique. Ce 7ᵉ bus achète des
tournées plus compactes (moins de temps à bord) **et de la marge** : la solution du CVRP à 6 bus pleins n'en a
aucune — **un élève de plus la rend infaisable**, alors qu'une inscription en cours d'année est le cas normal.

**Verdict : on garde MS6 + TSP** — pas par confort d'architecture, mais parce que la mesure le dit : pas de
surcoût en conduite, k TSP indépendants donc **parallélisables** (`/tournees` : 43 s → 9 s), et de la marge de
capacité. Le CVRP reste pertinent comme **outil de dimensionnement de flotte**, question à laquelle MS6 ne
répond pas.

> 📄 **Explication détaillée et pédagogique** : [`MS5_BENCHMARK_CVRP.md`](MS5_BENCHMARK_CVRP.md) — la question,
> le protocole, les obstacles rencontrés, la lecture des résultats et les questions probables du jury.
>
> Reproduire : `python notebooks/build_notebooks.py` puis exécuter `06_cvrp_benchmark.ipynb` (MS2 `:8082` et
> OSRM `:5000` requis). Figures : `notebooks/figures/06_*.png`.

## 9. Limites & perspectives (honnête)
- **TSP par bus** (l'affectation vient de MS6) — choix désormais **validé par mesure** (§ 8 ter) et non plus
  seulement par commodité. Le CVRP global a été implémenté (`cvrp.py`) et comparé ; il ne fait pas mieux à
  budget égal, mais sert d'outil de dimensionnement de flotte.
- Un **arrêt par élève** (porte-à-porte) ; l'agrégation en points d'arrêt communs = évolution.
- Pas de **fenêtres horaires** (time windows) ni de trafic temps réel — perspectives.

---

### 📂 Références
- Code : `ms5-planification/*.py` · Notebook : `ms5-planification/notebooks/05_vrp_study.ipynb`
- Résumé projet : `CLAUDE.md` (section MS5) · Console : `html_tests/test-console.html` (onglet 🗺️ Tournées)
