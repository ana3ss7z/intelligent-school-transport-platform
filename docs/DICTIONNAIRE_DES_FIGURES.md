# Dictionnaire des figures du mémoire

> **À quoi sert ce document.** Il décrit **les 30 figures** ajoutées aux notebooks des quatre
> briques IA, en langage simple. Pour chacune : ce qu'on voit, ce que ça veut dire, le chiffre à
> retenir, et où la placer dans le rapport.
>
> Écrit pour être lu **pendant la rédaction du mémoire** : chaque entrée peut servir de légende
> de figure presque telle quelle.

**Où sont les fichiers** — chaque figure existe en deux formats dans `notebooks/figures/` :

| Format | Usage |
|---|---|
| `.pdf` | **À utiliser dans le rapport** — vectoriel, net à toutes les tailles |
| `.png` | Aperçu rapide, 300 dpi |

Les mêmes images sont aussi visibles **dans les notebooks**, avec leur explication.

Pour tout regénérer (aucun service à allumer) :

```bash
cd ms11-analytique   && python notebooks/gen_figures_memoire.py
cd ms12-prediction   && python notebooks/gen_figures_memoire.py
cd ms6-clustering    && python notebooks/gen_figures_memoire.py
cd ms5-planification && python notebooks/gen_figures_memoire.py
```

---

## Vérification faite contre la production réelle — 29 août 2026

Les 13 services étaient allumés. Chaque chiffre affiché dans les figures a été comparé à ce que
répond le système **aujourd'hui**.

| Ce qui a été vérifié | Source interrogée | Résultat |
|---|---|---|
| MS6 — référence qualité (0,4256 · 734,2 m · 2804,1 m · 17 dispersés · 300 élèves · capacité 50) | `GET :8086/api/clustering/quality` | ✅ **identique** aux figures |
| MS6 — partition réellement en base | `GET /api/eleves` (300 élèves) | ✅ **k = 7**, tailles `[50, 50, 48, 44, 42, 37, 29]` |
| MS6 — la figure de l'arène décrit-elle cette partition ? | comparaison des coefficients de variation | ✅ **oui** — 0,1666 des deux côtés |
| MS6 — rayon désactivé en production ? | MS13 `ms6.rayon_max_m` | ✅ **0** — comme l'affirme la figure 06_8 |
| MS6 — distance routière aussi pour le recalcul auto ? | MS13 `ms6.use_road_for_auto` | ✅ **true** |
| MS11 — modèle gelé (iforest_curated, PR-AUC 0,9127, P 0,70, R 0,875) | `GET :8091/api/analytique/model-info` | ✅ **identique** |
| MS11 — les 4 seuils des règles live (90 km/h · 5 min · 250 m · 2 pings) | `GET :8091/api/analytique/live` **et** MS13 | ✅ **identiques** aux seuils testés |
| MS11 — `VITESSE_EXCESSIVE` a-t-elle un anti-rebond ? | MS13 `ms11.vitesse_pings_consecutifs` | ✅ **= 1**, donc **non** — le défaut pointé par les figures est toujours là |
| MS11 — la surveillance temps réel tourne-t-elle ? | `GET /live` → `surveillance_active` | ✅ **true** |
| MS12 — modèle gelé (elasticnet, MAE 1,3219, 26 variables, gain 52,7 %) | `GET :8088/api/eta/model-info` | ✅ **identique** |
| MS12 — mode de contexte | MS13 `ms12.contexte_mode` | ✅ **auto** (pas de valeurs forcées) |
| MS5 — budget du solveur (5 s par bus) | MS13 `ms5.vrp_time_limit_s` | ✅ **5** |

### Deux écarts trouvés — et corrigés le même jour

La vérification a trouvé deux figures qui ne décrivaient plus la production. **Les deux ont été
rejouées sur l'état actuel du système.**

#### Écart 1 — MS5 : le benchmark CVRP tournait sur une répartition disparue

| | Répartition des 7 bus | Écart-type des charges |
|---|---|--:|
| **En base aujourd'hui** | `50 · 50 · 48 · 44 · 42 · 37 · 29` | **7,14** |
| **Utilisée par le benchmark du 23/08** | `50 · 50 · 50 · 43 · 42 · 36 · 29` | **7,49** |

Le benchmark datait d'**avant** la migration vers k = 7 du 27 août. Même nombre de bus, mêmes
300 élèves — mais **pas les mêmes élèves dans les mêmes bus**.

✅ **Corrigé** : rejoué par `ms5-planification/rejouer_cvrp.py`, élèves lus en direct depuis MS2.
Les quatre figures MS5 et le document `MS5_BENCHMARK_CVRP.md` portent désormais les nouveaux
chiffres, et la campagne du 23/08 est conservée pour comparaison.

**Ce que le rejeu a confirmé** — le résultat structurel est **identique** : le CVRP se passe
toujours du 7ᵉ bus, en remplissant à 50/50 exactement. *Une conclusion qui survit à un changement
de données est plus solide qu'une conclusion obtenue une seule fois* — c'est l'objet de la nouvelle
figure `05_4_replication`.

**Ce que le rejeu a corrigé** — les écarts point par point ont bougé : le CVRP gagne au mieux
**0,9 %** (et non 0,2 %), la décomposition jusqu'à **3,7 %** (et non 2,3 %).

#### Écart 2 — MS6 : le balayage du rayon datait d'avant le correctif de `k`

Sa première ligne (« rayon désactivé », qui **est** la configuration de production) donnait
`k = 8` et une silhouette de `0,4056` — l'état d'avant le correctif du 24 août.

✅ **Corrigé** : rejoué par `ms6-clustering/rejouer_rayon.py` sur le code actuel. La ligne donne
maintenant **`k = 7` et `0,4256`**, exactement ce que publie `GET /api/clustering/quality`.
*Au passage, cela vérifie que le correctif de `choisir_k` fonctionne bien.*

#### Un défaut de méthode trouvé en cours de route

En rejouant, j'ai mesuré la reproductibilité du solveur — et **le document affirmait quelque chose
de faux**.

| Instance | Répétitions | Étendue mesurée |
|---|--:|--:|
| TSP, un bus, 50 arrêts, 5 s | 5 | **0,00 %** |
| CVRP, 7 bus, 300 arrêts, 35 s | 3 | **0,00 %** |

Le document annonçait « environ 3 % de bruit de solveur ». Ce chiffre venait d'un contrôle qui
comparait **deux groupes d'élèves différents** : ce n'était pas du bruit, c'était une autre
instance. Le vrai bruit, mesuré entre deux exécutions séparées, vaut **0,55 %**.

> **Pourquoi ça compte** : un bruit surestimé sert d'argument pour écarter des écarts réels. Avec
> 3 % annoncés, l'avantage de 3,7 % de la décomposition passait pour du hasard. Avec 0,55 %, il est
> significatif.

> ✅ **Les 30 figures décrivent désormais le système tel qu'il tourne.**

---

# MS11 — Détection des anomalies

📁 `ms11-analytique/notebooks/figures/` · 📓 `04_anomaly_detection.ipynb` (section D)

> **Le contexte, en une phrase** : MS11 contient **deux surveillances différentes**. Un modèle
> d'apprentissage qui analyse un trajet **une fois terminé**, et **trois règles simples** qui
> examinent **chaque position GPS pendant** le trajet. Ce sont les règles qui déclenchent les
> vraies alertes — et elles n'avaient jamais été mesurées.

---

### `11_A1_couverture_spatiale_deviation`
**Ce qu'on voit** — une courbe qui monte : plus le bus s'écarte de sa route, plus l'alerte a de
chances de se déclencher. La zone grise au-dessus est ce que l'alerte **rate**.

**Ce que ça veut dire, simplement** — *si un bus quitte son itinéraire de 300 mètres, l'alerte ne
se déclenche que sur 29 % du parcours. Les 71 % restants, personne n'est prévenu.*

**Pourquoi c'est ainsi** — un bus fait 50 arrêts et repasse sans arrêt dans le même quartier. Quand
il se trompe de rue, il se retrouve souvent à côté d'**un autre morceau de sa propre tournée** —
celui qu'il empruntera dans dix minutes. Le programme croit donc qu'il est encore sur sa route.

**Chiffre à retenir** — **un détour de 400 m laisse le bus à seulement 174 m de sa tournée.**

**Où la mettre** — c'est **la figure la plus importante de MS11**. À placer là où on parle des
limites du système, ou dans les perspectives.

---

### `11_A2_couverture_par_seuil`
**Ce qu'on voit** — trois courbes (détours de 200, 300 et 400 m). Quand on baisse le seuil de
réglage, les trois montent.

**Ce que ça veut dire** — *le réglage actuel est trop prudent. En passant de 250 m à 120 m, on
détecterait deux fois plus de détours, sans déclencher une seule fausse alerte en plus.*

**Chiffre à retenir** — sur un détour de 300 m : **29 % de détection à 250 m, 55 % à 120 m**.
Et **zéro fausse alerte** dans les deux cas, même avec un GPS imprécis de 30 m.

**Où la mettre** — juste après la précédente : elle montre qu'on sait déjà comment faire mieux.

---

### `11_A3_balayages_temporels`
**Ce qu'on voit** — deux graphiques de réglage. À gauche, l'anti-rebond (combien de mesures
consécutives avant d'alerter). À droite, la durée d'arrêt qui déclenche « panne ».

**Ce que ça veut dire** — *les deux réglages actuels sont bons, et on peut maintenant le prouver au
lieu de le supposer.*

**Chiffre à retenir** — exiger **2 mesures au lieu d'1** supprime **3,34 fausses alertes par heure**
et ne coûte que **5 secondes** de retard.

**Où la mettre** — dans la partie « réglage des paramètres ». C'est l'exemple type d'un choix
transformé en mesure.

---

### `11_A4_scenarios_rejeu`
**Ce qu'on voit** — à gauche, pour chaque incident testé : le temps **minimum imposé par le
réglage** (point gris) et le temps **réellement mis** (point bleu). À droite, les situations où le
système doit rester silencieux.

**Ce que ça veut dire** — *quand une panne dure 8 minutes, l'alerte arrive 5 secondes après le
minimum possible : le programme n'ajoute presque rien. Sauf pour la déviation, qui perd 75 secondes.*

**Chiffre à retenir** — la seule fausse alerte du banc d'essai vient d'**une mesure GPS aberrante à
200 km/h**. La règle de vitesse n'a **aucune protection** contre ça (vérifié encore aujourd'hui).

**Où la mettre** — pour montrer que le système a été testé sérieusement, scénario par scénario.

---

### `11_B1_rappel_par_nature`
**Ce qu'on voit** — pour 4 méthodes de détection, combien d'anomalies de chaque **type** elles
attrapent : les évidentes (« franc »), celles qui dépendent du contexte, et les surcharges.

**Ce que ça veut dire** — *aucune méthode n'est meilleure que les autres partout. Elles se
complètent.*

**Chiffre à retenir** — la méthode **simple** attrape les anomalies de contexte **12 fois sur 14**,
le modèle d'apprentissage seulement **3 fois sur 14**. Mais le modèle est le seul à voir les
surcharges (**7/7 contre 3/7**).

**Où la mettre** — c'est **le résultat central de MS11**. La documentation du projet affirmait
exactement l'inverse ; le montrer prouve qu'on a vérifié au lieu de recopier.

---

### `11_B2_incertitude_classement`
**Ce qu'on voit** — à gauche, chaque méthode avec sa **barre d'incertitude**. À droite, le classement
obtenu quand on teste sur beaucoup plus de cas.

**Ce que ça veut dire** — *le classement publié reposait sur 8 anomalies seulement. Avec 38, le
gagnant change.*

**Chiffre à retenir** — le modèle d'apprentissage passe de **0,9127 à 0,847**, la méthode simple de
0,8043 à **0,926**. **Le gagnant s'inverse.**

**Où la mettre** — dans la partie méthode. C'est l'illustration parfaite de « combien
d'observations séparent vraiment ces deux résultats ? ».

---

### `11_B3_pr_auc_par_bloc`
**Ce qu'on voit** — la qualité de chaque méthode sur 4 périodes de test successives.

**Ce que ça veut dire** — *le premier bloc est le seul où le modèle d'apprentissage gagne. C'est
malheureusement celui qui avait été choisi pour le benchmark officiel.*

**Chiffre à retenir** — **1 bloc favorable sur 4**.

**Où la mettre** — juste après la précédente : elle explique *d'où vient* l'inversion.

---

### `11_B4_fuite_generateur`
**Ce qu'on voit** — à gauche, les coefficients utilisés par le programme comparés à ceux
**retrouvés uniquement à partir des données**. À droite, l'effet sur la qualité de détection.

**Ce que ça veut dire** — *on soupçonnait la méthode gagnante de « connaître la réponse à l'avance ».
Ce n'est pas le cas : elle marche aussi bien sans.*

**Chiffre à retenir** — en recalculant tout depuis les données seules, la méthode gagnante fait même
**+0,003 de mieux**.

**Où la mettre** — c'est la réponse à une question que le jury peut poser. Le fait de se l'être
posée soi-même compte autant que la réponse.

---

### `11_B5_budget_alerte`
**Ce qu'on voit** — ce qui se passe quand on autorise plus ou moins d'alertes par jour.

**Ce que ça veut dire** — *la vraie question de l'administration n'est pas « quel score ? » mais
« combien d'alertes puis-je traiter par jour ? ». Cette courbe permet d'en discuter avec elle.*

**Chiffre à retenir** — en acceptant **2 %** d'alertes, le modèle attrape **100 %** des anomalies
de cette période.

**Où la mettre** — dans la partie exploitation, pas dans la partie technique.

---

### `11_B6_union_budget_egal`
**Ce qu'on voit** — ce que donne la **combinaison** des deux méthodes, à nombre d'alertes égal.

**Ce que ça veut dire** — *combiner les deux semble évident, mais ça ne donne pas le meilleur des
deux : ça donne un intermédiaire.*

**Chiffre à retenir** — la combinaison récupère les surcharges (**6/7**) mais perd du contexte
(**7/14** au lieu de 12/14).

**Où la mettre** — pour montrer qu'on a testé l'idée évidente au lieu de l'affirmer.

---

# MS12 — Prédiction de l'heure d'arrivée

📁 `ms12-prediction/notebooks/figures/` · 📓 `01_eta_data_study`, `02_model_comparison`,
`03_production_strategy`

> **Le contexte, en une phrase** : le modèle a appris sur des **petits bouts de trajet** (0,7 à
> 4 km), mais les applications lui demandent le **trajet entier restant** (6 à 12 km). Un
> garde-fou l'empêche d'aller au-delà de ce qu'il connaît — et ce garde-fou n'avait aucune mesure.

---

### `12_8_domaine_entrainement` *(dans `01_eta_data_study`)*
**Ce qu'on voit** — deux séries de barres qui **ne se touchent pas** : à gauche ce que le modèle a
appris, à droite ce qu'on lui demande.

**Ce que ça veut dire** — *demander une tournée de 12 km à un modèle entraîné sur 4 km maximum,
c'est lui demander trois fois plus que ce qu'il a vu.*

**Chiffre à retenir** — domaine d'apprentissage : **0,69 à 3,99 km**. Demandes réelles : **6 à
12 km**.

**Où la mettre** — c'est la figure qui **justifie l'existence du garde-fou**. À placer avant de
l'expliquer.

**⚠️ À signaler aussi** — les barres sont des pics parce que le générateur de données n'a que
**12 valeurs de durée différentes**. C'est une limite du projet, et il vaut mieux la dire soi-même :
un modèle simple retrouve facilement une formule aussi régulière.

---

### `12_2_significativite_bootstrap` *(dans `02_model_comparison`)*
**Ce qu'on voit** — les 10 modèles perdants, chacun avec une **barre d'incertitude**. La ligne
rouge marque l'égalité avec le gagnant.

**Ce que ça veut dire** — *le gagnant ne l'emporte que de 2,7 secondes. On a vérifié que ce n'est
pas de la chance : c'est un vrai écart.*

**Chiffre à retenir** — **les 10 barres sont entièrement à droite du zéro** : le gagnant bat
vraiment tout le monde.

**Où la mettre** — juste après le tableau de comparaison des modèles.

**Détail honnête à raconter** — *on s'attendait au contraire.* 2,7 secondes ressemblent à du bruit.
La mesure a corrigé l'intuition — c'est son rôle.

---

### `12_3_reglage_arbres` *(dans `02_model_comparison`)*
**Ce qu'on voit** — deux modèles « forêts », avant et après réglage. La ligne rouge est le gagnant.

**Ce que ça veut dire** — *on nous dirait : « vos forêts perdent parce que vous ne les avez pas
réglées ». C'est vrai qu'elles s'améliorent. Mais elles restent derrière.*

**Chiffre à retenir** — XGBoost gagne **17 %** au réglage… et reste au-dessus du gagnant
(1,3945 contre **1,3219**).

**Où la mettre** — pour désamorcer l'objection avant qu'on la pose.

---

### `12_4_baseline_historique` *(dans `02_model_comparison`)*
**Ce qu'on voit** — le modèle comparé à **deux** points de comparaison : la moyenne des jours
précédents, et l'estimation brute de la carte routière.

**Ce que ça veut dire** — *le gain annoncé de 52,7 % était mesuré contre le plus faible des deux.
Contre ce qu'un gestionnaire ferait vraiment avec un tableur, le gain est de 44 %.*

**Chiffre à retenir** — **44 %**, pas 52,7 %.

**Où la mettre** — dans les résultats. Annoncer 44 % est **plus solide** que 52,7 %, parce que c'est
la comparaison que le jury fera spontanément.

---

### `12_7_cout_vs_precision` *(dans `02_model_comparison`)*
**Ce qu'on voit** — chaque modèle placé selon son **temps d'entraînement** et sa **précision**.

**Ce que ça veut dire** — *ici, le meilleur modèle est aussi le plus rapide. Ce n'est pas toujours
le cas, donc il fallait le vérifier.*

**Chiffre à retenir** — le gagnant est **mille fois plus rapide** que les modèles complexes.

**Où la mettre** — pour justifier que le choix est aussi bon en exploitation, pas seulement sur le
papier.

---

### `12_1_garde_anti_extrapolation` *(dans `03_production_strategy`)*
**Ce qu'on voit** — quatre mesures d'erreur, pour trois façons de prédire : celle utilisée en vrai,
celle qui consisterait à forcer le modèle, et l'estimation brute de la carte.

**Ce que ça veut dire** — *la solution en place est bien la meilleure des trois, et de loin.*

**Chiffre à retenir** — **37 % d'erreur en moins** qu'en forçant le modèle, **77 % en moins** que
la carte seule.

**Où la mettre** — c'est **la figure la plus importante de MS12**. Elle valide la décision la plus
subtile du projet, qui n'avait aucune preuve jusque-là.

**Comment expliquer le principe en une phrase** — *le modèle dit de combien la circulation se
dégrade aujourd'hui ; la carte routière dit la distance. On multiplie l'un par l'autre.*

---

### `12_5_correction_biais` *(dans `03_production_strategy`)*
**Ce qu'on voit** — l'erreur et le décalage moyen, avant et après une correction très simple : une
soustraction.

**Ce que ça veut dire** — *les deux tiers de l'erreur du modèle sont un décalage constant. Le
retirer ferait gagner 15 % de précision.*

**Chiffre à retenir** — erreur de **0,859 → 0,733 minute** en soustrayant **0,515 minute**.

**Où la mettre** — dans les perspectives d'amélioration.

**⚠️ Le revers, qu'il faut dire** — cette correction déplace le problème : sur l'ensemble des
trajets, le décalage passe de +0,07 à −0,44. Le système annonçait un peu trop tard, il annoncerait
un peu trop tôt. **C'est un choix, pas un gain gratuit.**

---

### `12_6_ablation_familles` *(dans `03_production_strategy`)*
**Ce qu'on voit** — pour chaque groupe de variables, ce que le modèle **perd** si on l'enlève. À
droite du zéro : retirer dégrade. À gauche : retirer améliore.

**Ce que ça veut dire** — *la météo et la circulation portent presque tout. Deux groupes de
variables ne servent à rien — et le modèle irait même un peu mieux sans eux.*

**Chiffres à retenir** —
- sans météo ni circulation : **+0,48 minute d'erreur** (le modèle s'effondre) ;
- variables marocaines (ramadan, jour de souk) : **+0,10 minute** — donc **utiles**, la question
  viendra ;
- sans le remplissage du bus : **−0,02 minute**, le modèle **s'améliore**.

**Où la mettre** — dans l'analyse du modèle. C'est aussi la meilleure réponse à « à quoi servent
vos variables marocaines ? ».

**La leçon à écrire** — *l'importance d'une variable dit ce que le modèle **utilise**. L'ablation
dit ce qu'il **perdrait**. Ce n'est pas la même chose* : une variable classée 7ᵉ en importance ne
vaut que 0,003 minute en ablation.

---

# MS6 — Répartition des élèves dans les bus

📁 `ms6-clustering/notebooks/figures/` · 📓 `clustering_study`, `02_model_comparison`,
`03_production_strategy`, `06_rayon_max_study`

---

### `06_1_arene_complete` *(dans `02_model_comparison`)*
**Ce qu'on voit** — 6 méthodes de répartition comparées sur 4 mesures. En rouge : celle utilisée en
vrai. Les barres hachurées grises sont des méthodes **impossibles à appliquer**.

**Ce que ça veut dire** — *on compare enfin la vraie méthode du projet à des méthodes simples, avec
la même règle de notation pour tout le monde.*

**Chiffres à retenir** —
- contre « un bus par quartier » : **14,6 % de conduite en moins** et **4,7 minutes de bus en moins
  par enfant, chaque matin** ;
- contre une répartition au hasard : **+110 %** — la géographie est bien le premier levier ;
- refuser les solutions impossibles coûte **3,4 %**.

**Où la mettre** — dans les résultats de MS6. C'est la réponse à *« votre algorithme fait-il mieux
qu'un simple découpage par quartier ? »*, question à laquelle le projet ne savait pas répondre.

**Le point de méthode à expliquer** — les méthodes calculées « à vol d'oiseau » sont **notées sur
les distances routières**, comme les autres. Sinon chacune serait jugée avec sa propre règle, et la
comparaison ne voudrait rien dire.

---

### `06_2_ablation_distance_routiere` *(dans `03_production_strategy` et `clustering_study`)*
**Ce qu'on voit** — la même méthode, lancée deux fois : une fois avec les vraies distances par la
route, une fois à vol d'oiseau. **Rien d'autre ne change.**

**Ce que ça veut dire** — *utiliser les vraies routes ne rend pas les groupes « plus jolis ». Ça
raccourcit le temps que chaque enfant passe dans le bus.*

**Chiffres à retenir** —
- indice de qualité : **+0,0019** — invisible ;
- temps de conduite : **−3,7 minutes** ;
- **temps dans le bus par enfant : −1,7 minute**, soit près de 10 %.

**Où la mettre** — c'est **le résultat le plus important de MS6**. À placer là où on justifie le
choix des distances routières.

**La leçon à écrire** — *l'indice de qualité qu'on regardait ne voyait pas l'effet. Il fallait
changer de mesure, pas d'algorithme.* Sur 300 élèves et deux trajets par jour, ce sont **17 heures
d'enfant économisées chaque jour**.

---

### `06_3_bruit_silhouette_par_k` *(dans `03_production_strategy`)*
**Ce qu'on voit** — pour 6, 7, 8 et 9 bus : la qualité obtenue, avec sa **zone d'incertitude**.

**Ce que ça veut dire** — *l'écart entre 8 bus et 9 bus est plus petit que l'imprécision du calcul.
Choisir « le meilleur » revenait donc à tirer au sort.*

**Chiffre à retenir** — **7 bus est très stable (± 0,0001)**, mais 8 et 9 bus varient de **±0,012 et
±0,020** — plus que ce qui les sépare.

**Où la mettre** — juste avant la figure suivante : elle en donne la **cause**.

**L'image à utiliser** — *une balance qui se trompe de 100 grammes ne peut pas départager deux sacs
qui diffèrent de 50 grammes.*

---

### `06_4_sensibilite_ordre` *(dans `03_production_strategy` et `clustering_study`)*
**Ce qu'on voit** — à gauche : sur 30 essais avec **exactement les mêmes élèves**, le programme
répond parfois 7 bus, parfois 8, parfois 9. À droite : les qualités obtenues.

**Ce que ça veut dire** — *le nombre de bus n'était pas une propriété des données. Il dépendait de
l'ordre dans lequel la base renvoyait les élèves.*

**Chiffre à retenir** — **7 bus dans 57 % des cas, 9 bus dans 37 %.** Deux bus et deux chauffeurs
d'écart, sans qu'aucune donnée n'ait changé.

**Où la mettre** — c'est **le défaut le plus marquant trouvé dans le projet**. Excellent pour la
partie « ce que la vérification a révélé ».

**Le point à ne pas rater** — le programme **réécrit les élèves en base à chaque calcul**, ce qui
change justement cet ordre. **Appliquer une répartition pouvait donc changer la suivante.** Une
inscription en cours d'année devenait un tirage au sort sur la flotte.

---

### `06_5_churn_par_regle` *(dans `03_production_strategy`)*
**Ce qu'on voit** — pour trois façons de choisir le nombre de bus : combien d'élèves changent de bus
quand un seul nouvel élève s'inscrit.

**Ce que ça veut dire** — *c'est ce que les familles subissent réellement, et ce n'était mesuré
nulle part.*

**Chiffre à retenir** — avec l'ancienne règle, le nombre de bus changeait **9 fois sur 15
inscriptions**, et chaque fois **12 à 13 % des élèves** changeaient de bus — **une trentaine
d'enfants pour une seule inscription**.

**Où la mettre** — pour montrer qu'on a mesuré l'effet **sur les usagers**, pas seulement sur un
indice technique.

**Le détail honnête** — la règle « robuste » seule a un **pire** cas plus mauvais (25,4 %). C'est ce
qui a obligé à ajouter un second mécanisme. *La mesure a corrigé la première proposition.*

---

### `06_6_correctif_mesure` *(dans `03_production_strategy`)*
**Ce qu'on voit** — avant / après la correction du 24 août, sur les deux questions : combien
d'élèves déplacés, et le tirage au sort a-t-il disparu.

**Ce que ça veut dire** — *après correction, 30 essais sur 30 donnent la même réponse : 7 bus, et
une seule répartition.*

**Chiffres à retenir** —
- élèves déplacés par inscription : **6,42 % → 1,02 %** ;
- changements de flotte : **9 → 0** ;
- **30 essais sur 30 donnent 7 bus.**

**Où la mettre** — juste après le problème. C'est la démonstration que la correction fonctionne.

**⚠️ À dire aussi** — la correction a coûté **une fois** le déplacement de 22 élèves sur 300 (7,3 %).
C'était prévu et mesuré à l'avance.

---

### `06_7_garde_fou_qualite` *(dans `03_production_strategy`)*
**Ce qu'on voit** — les quatre niveaux de référence utilisés pour juger la qualité d'une
répartition.

**Ce que ça veut dire** — *le système d'alerte qualité s'était bloqué tout seul pendant cinq
semaines.*

**Comment c'est possible, simplement** — la référence n'est mise à jour **que si le résultat est
jugé bon**. Une référence trop haute rend donc tous les résultats « mauvais »… ce qui l'empêche
d'être corrigée. **Trop haute → tout est mauvais → jamais corrigée → toujours trop haute.**

**Chiffre à retenir** — une référence de **0,5183** écrite le 17 juillet a jugé pendant cinq
semaines des résultats dont le maximum atteignable était **0,4256**.

**Où la mettre** — dans la partie sur la surveillance de la qualité.

**⚠️ Le piège à mentionner** — la correction qui vient à l'esprit (« mettre à jour la référence même
quand c'est mauvais ») **détruirait** le garde-fou : chaque résultat serait comparé au précédent un
peu moins bon, et une dégradation lente ne serait jamais détectée.

---

### `06_8_rayon_arbitrage` *(dans `06_rayon_max_study`)*
**Ce qu'on voit** — quand on impose une distance maximale entre l'élève et son point de ramassage :
la qualité monte (courbe), mais le nombre d'élèves **sans bus** explose (barres rouges).

**Ce que ça veut dire** — *l'indice de qualité s'améliore parce qu'on a retiré les élèves difficiles
de la répartition, pas parce que le regroupement est meilleur.*

**Chiffre à retenir** — à 800 m, la qualité atteint **0,7955** — presque le double. Mais **156
élèves sur 300 n'ont plus de bus**.

**Où la mettre** — excellente conclusion pour la partie MS6, ou dans la discussion sur les limites
des indices de qualité.

**La phrase à retenir** — **un indice de qualité ne se lit jamais sans savoir sur combien de
personnes il a été calculé.**

**Vérifié en production** — le rayon est bien **désactivé** (`ms6.rayon_max_m = 0`).

---

# MS5 — Ordre de passage des bus

📁 `ms5-planification/notebooks/figures/` · 📓 `06_cvrp_benchmark.ipynb`

> ✅ **Rejouées le 29/08** sur la partition de production, élèves lus en direct depuis MS2
> (`rejouer_cvrp.py`). Les chiffres ci-dessous sont ceux du système actuel.

> **Le contexte, en une phrase** : le système résout le problème en **deux temps** — d'abord *quel
> élève dans quel bus* (MS6), puis *dans quel ordre* (MS5). Il existe une méthode qui fait les deux
> d'un coup. La question était : **combien nous coûte le fait d'avoir découpé le problème ?**

---

### `05_1_ecart_vs_taille`
**Ce qu'on voit** — à gauche, les deux méthodes comparées sur 6 tailles de problème. À droite,
l'écart entre elles.

**Ce que ça veut dire** — *découper le problème ne coûte rien. Et surtout, ça ne coûte pas plus cher
quand le problème grossit.*

**Chiffre à retenir** — la méthode « tout d'un coup » ne gagne **au mieux que 0,9 %**, et perd
jusqu'à **3,7 %**.

**Où la mettre** — dans les résultats de MS5. La bonne question n'était pas « qui gagne ? » mais
**« l'écart grandit-il avec la taille ? »** — et il fallait six mesures pour y répondre.

**L'explication à écrire** — *MS6 regroupe déjà les élèves selon les vraies distances par la route.
L'information géographique est donc donnée au problème **avant** de calculer les tournées. L'autre
méthode part de zéro et doit tout redécouvrir en 35 secondes.* **Découper n'est pas une
approximation qu'on subit : c'est une façon de donner au calculateur ce qu'on sait déjà du terrain.**

---

### `05_2_equilibrage_flotte`
**Ce qu'on voit** — à gauche, le nombre de bus réellement utilisés. À droite, à quel point les bus
sont remplis de façon égale.

**Ce que ça veut dire** — *avec 7 bus disponibles, l'autre méthode n'en utilise que 6, remplis
exactement à 50 places. Un bus — donc un chauffeur — économisé.*

**Chiffre à retenir** — **6 bus au lieu de 7**, pour **+0,6 %** de temps de conduite.

**Le point fort** — c'est le résultat **le plus robuste** du benchmark : identique dans les deux
campagnes, sur deux répartitions différentes.

**Où la mettre** — c'est **le résultat le plus intéressant de MS5**, et il était caché derrière la
colonne des durées.

**Ce qu'il faut absolument ajouter** — *ce n'est pas une erreur de MS6, c'est un choix différent.*
Le 7ᵉ bus achète deux choses que la colonne « durée » ne montre pas : des tournées plus courtes pour
chaque enfant, et de la **marge**. Avec 6 bus pleins, **un seul élève de plus rend le problème
impossible** — or une inscription en cours d'année est normale dans une école.

**Et la conclusion** — le perdant n'est pas jeté : il devient l'outil qui répond à *« combien de bus
me faut-il au minimum ? »*.

---

### `05_3_cout_calcul`
**Ce qu'on voit** — le temps de calcul accordé, et le temps d'attente réel quand les calculs se font
en parallèle.

**Ce que ça veut dire** — *sept petits calculs indépendants peuvent tourner en même temps. Un gros
calcul unique, non.*

**Chiffre à retenir** — en production, ce parallélisme fait passer le calcul de **43 secondes à
9 secondes**.

**Où la mettre** — pour justifier le choix d'architecture, pas seulement le choix d'algorithme.

**La réponse à préparer** — *« pourquoi ne pas laisser tourner l'autre méthode plus longtemps ? »*
On pourrait, et elle finirait par rattraper. Mais si on accorde plus de temps, **la méthode découpée
en profite aussi** — et sans faire attendre plus longtemps.

---

### `05_4_replication`
**Ce qu'on voit** — à gauche, les résultats des **deux campagnes** (23/08 et 29/08) mis côte à
côte. À droite, les deux résultats structurels.

**Ce que ça veut dire** — *le benchmark a été refait sur la nouvelle répartition des élèves. Les
écarts détaillés changent — ce sont d'autres données — mais la conclusion, elle, ne change pas.*

**Chiffre à retenir** — le CVRP se passe du 7ᵉ bus, avec un écart-type de charge de **0,00**, dans
**les deux campagnes**.

**Où la mettre** — c'est une **figure de méthode**, pas de résultat. Elle montre qu'on a vérifié la
solidité de sa propre conclusion au lieu de la publier une fois pour toutes.

**L'argument à en tirer** — *une conclusion qui survit à un changement de données est plus solide
qu'une conclusion obtenue une seule fois.* C'est aussi l'application de la règle 7 du protocole du
projet : **consommer la même source de données que le service**.

**À dire si on demande « votre calcul est-il déterministe ? »** — **oui**, c'est mesuré : la même
tournée résolue 5 fois donne exactement le même résultat (étendue 0,00 %). Une petite variation
apparaît seulement entre deux exécutions séparées du programme : **0,55 %**.
*(Le document affirmait « environ 3 % » avant cette vérification — c'était une erreur, expliquée en
haut de ce dictionnaire.)*

---

# Aide-mémoire : les 8 figures à retenir si le rapport doit être court

| Ordre | Figure | La phrase qu'elle prouve |
|--:|---|---|
| 1 | `06_2_ablation_distance_routiere` | Les vraies routes font gagner **1,7 minute de bus par enfant** |
| 2 | `06_1_arene_complete` | On fait **14,6 % mieux** qu'un simple découpage par quartier |
| 3 | `12_1_garde_anti_extrapolation` | Le garde-fou de prédiction divise l'erreur par **quatre** |
| 4 | `11_A1_couverture_spatiale_deviation` | L'alerte de déviation est **aveugle sur 70 %** du parcours |
| 5 | `05_2_equilibrage_flotte` | Un **bus et un chauffeur** peuvent être économisés |
| 6 | `06_4_sensibilite_ordre` | Le nombre de bus était **tiré au sort** entre 7 et 9 |
| 7 | `11_B1_rappel_par_nature` | Les deux détecteurs sont **complémentaires**, aucun ne domine |
| 8 | `12_6_ablation_familles` | Le modèle **irait mieux** avec 10 variables de moins |

---

# Ce que ces figures ont en commun — le fil du mémoire

Les quatre briques ont été passées au même filtre, et **dans les quatre cas la mesure a contredit
ou nuancé une affirmation du dossier**. Trois enseignements traversent toutes ces figures :

1. **La métrique choisie décide du gagnant.** Dans MS6, l'indice de qualité et le temps passé dans
   le bus désignent **deux méthodes différentes**. Il fallait décider ce qu'on optimise **avant** de
   comparer.
2. **Il faut mesurer le code qui tourne vraiment.** MS6 comparait dix algorithmes sans que celui
   déployé y figure ; MS11 notait le modèle pendant que les vraies alertes venaient des règles ;
   MS12 publiait des chiffres qui ne valaient plus dans son mode de fonctionnement réel. La question
   qui l'a révélé : **« quel code s'exécute quand un parent ouvre l'application ? »**
3. **Un classement doit dire sur combien d'observations il repose.** MS11 changeait de gagnant en
   passant de 8 à 38 cas. MS12, à l'inverse, avait un écart de 2,7 secondes qui s'est révélé
   **réel**. *L'incertitude ne va pas toujours dans le sens qu'on croit.*

> Protocole complet : [`PROTOCOLE_BENCHMARK_IA.md`](PROTOCOLE_BENCHMARK_IA.md) ·
> détails par brique : [MS5](MS5_BENCHMARK_CVRP.md) · [MS6](MS6_BENCHMARK_DISTANCE.md) ·
> [MS11](MS11_BENCHMARK_REGLES_LIVE.md) · [MS12](MS12_BENCHMARK_GARDE_ET_ABLATION.md)
