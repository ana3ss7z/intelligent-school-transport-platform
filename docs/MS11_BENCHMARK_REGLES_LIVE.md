# MS11 — ce que la mesure a dit, et qui n'était pas ce qu'on croyait

> **Document pédagogique.** Il applique à MS11 le protocole du [benchmark CVRP](MS5_BENCHMARK_CVRP.md).
> Deux des trois résultats **contredisent la documentation existante du projet**. Ils sont rapportés
> tels quels : c'est la seule façon de faire d'un benchmark autre chose qu'une justification.
>
> Code : [`replay.py`](../ms11-analytique/replay.py) · [`ablation_anomaly.py`](../ms11-analytique/ablation_anomaly.py)
> Résultats : [`data/live_rules_benchmark.json`](../ms11-analytique/data/live_rules_benchmark.json) ·
> [`data/ablation_anomaly.json`](../ms11-analytique/data/ablation_anomaly.json)

---

## 1. Le point de départ : on évaluait la moitié du service

MS11 contient **deux détecteurs de nature différente** :

| | Détecteur ML | Règles live |
|---|---|---|
| Quoi | Isolation Forest sur un **trajet complet** | 3 règles de seuil sur **chaque ping GPS** |
| Quand | à la demande, *après* le trajet | en continu, *pendant* le trajet |
| Ce qu'il déclenche | un tableau d'analyse | **les vraies alertes d'exploitation** |
| Évaluation avant ce travail | benchmark 4 détecteurs, split temporel, PR-AUC 0,91 | **aucune** |

Les règles live avaient pour seule vérification un test de fumée binaire dans
`e2e_integration_test.py` (« on pousse 200 km/h, une alerte sort ») et **une** mesure manuelle
notée dans `CLAUDE.md`. Leurs quatre seuils — **90 km/h · 5 min · 250 m · 2 pings** — étaient posés
à dire d'expert. Aucune courbe ne disait ce qu'on gagne ou perd en les déplaçant.

---

## 2. Comment on mesure des règles temps réel hors ligne

`live_monitor.observer(bus_id, lat, lng, vitesse, ts)` est une **fonction pure à état de module**.
Elle se rejoue donc sans RabbitMQ, sans backend, sans OSRM. Il suffit de lui fournir une trace.

**Le support n'est pas une géométrie de laboratoire** : on rejoue sur la **vraie tournée du
groupe 1** produite par MS5 — 753 points, 17 250 m, 35,99 min, soit 28,8 km/h de moyenne — la même
fixture qui sert aux tests de parité ETA des deux applications Flutter. On y **injecte des
événements datés** (arrêt de N minutes, pointe de vitesse, décalage latéral de X mètres pendant
Y pings), ce qui donne une vérité terrain exacte : on sait ce qui aurait dû sortir, et quand.

Trois métriques, dans cet ordre d'importance métier :

1. **Fausses alarmes par heure** — une alerte qui crie au loup est désactivée par l'administration
   en trois jours. C'est la métrique qui décide de la survie d'une fonctionnalité.
2. **Latence de détection**, comparée au **plancher théorique** de la règle. Séparer les deux
   distingue ce qu'on a *choisi* (un seuil de 5 min impose 5 min d'attente) de ce que
   l'implémentation *ajoute*.
3. **Taux de détection**.

---

## 3. Premier résultat : la règle de déviation est largement aveugle

C'est le résultat le plus important du document, et il n'était pas attendu.

Un détour de **260 m** avec un seuil à **250 m** n'a **pas** été détecté. Vérification faite,
ce n'est pas le banc d'essai qui se trompe :

| Détour nominal | Écart réellement mesuré à la polyligne (min / médian / max) | Part du parcours où il serait détecté |
|--:|---|--:|
| 100 m | 0 / 85 / 100 m | **0 %** |
| 200 m | 0 / 97 / 200 m | **0 %** |
| 250 m | 1 / 120 / 250 m | 9,6 % |
| 300 m | 1 / 149 / 300 m | 29,2 % |
| 400 m | 2 / 174 / 400 m | 35,8 % |
| 800 m | 1 / 359 / 800 m | 61,2 % |

**Un bus décalé de 400 m de son itinéraire n'est en moyenne qu'à 174 m de sa propre tournée.**

### Pourquoi

La règle mesure la distance au point le plus proche de **toute** la polyligne. Or une tournée de
50 arrêts repasse sans cesse dans le même quartier : le bus dévié se retrouve à côté d'un **autre
tronçon de sa propre tournée**, qu'il empruntera dans dix minutes ou qu'il a quitté il y a cinq.
Géométriquement, il est « sur la route » ; opérationnellement, il n'y est pas.

### C'est un piège que le projet connaît déjà

C'est **exactement** le piège n° 13 de `CLAUDE.md` — celui du *cycle fermé* qui faisait bondir
l'ETA de 1,1 à 35,4 minutes à l'arrivée à l'école. Le remède y est déjà écrit et éprouvé :
`depuisAlongM`, un **plancher de progression** qui interdit à la projection de rembobiner. La règle
de déviation n'en a aucun équivalent : elle ignore complètement *où en est* le bus dans sa tournée.

> **Correctif recommandé** (hors périmètre de ce benchmark, à décider) : restreindre la projection
> à une fenêtre autour de l'abscisse déjà atteinte, exactement comme `routeEta`. La primitive
> existe en trois implémentations et est vérifiée sur cette même tournée.

### En attendant : le seuil de 250 m est trop haut

Le balayage bruit × seuil montre que **le bruit GPS n'est pas l'adversaire qu'on croyait** :

| Seuil | σ = 0 m | σ = 5 m | σ = 15 m | σ = 30 m |
|--:|---|---|---|---|
| 50 m | 0 FA/h | 0 FA/h | 0 FA/h | **1,67 FA/h** |
| 100 m | 0 FA/h | 0 FA/h | 0 FA/h | 0 FA/h |
| 250 m | 0 FA/h | 0 FA/h | 0 FA/h | 0 FA/h |

Aucune fausse alarme dès 100 m, **même à 30 m de bruit** — soit bien au-delà de l'erreur GPS
urbaine courante. Le seuil actuel achète donc une marge dont on n'a pas besoin, et la paie cher :

| Seuil | Détour 200 m | Détour 300 m | Détour 400 m |
|--:|--:|--:|--:|
| 100 m | 48,3 % | 58,8 % | 64,2 % |
| **120 m** | **43,8 %** | **54,6 %** | **59,2 %** |
| 250 m *(actuel)* | 0 % | 29,2 % | 35,8 % |

**Passer de 250 m à 120 m ferait presque doubler la couverture (29 % → 55 % sur un détour de
300 m) sans aucune fausse alarme mesurée.** C'est un réglage gratuit.

---

## 4. Deuxième résultat : l'anti-rebond est bien réglé, et on peut le prouver

Le paramètre `deviation_pings_consecutifs = 2` était un choix de bon sens. Mesuré, à seuil abaissé
à 100 m et bruit σ = 30 m — c'est-à-dire dans les conditions où le bruit devient un vrai adversaire :

| Pings consécutifs | Fausses alarmes/h | Détour détecté | Latence |
|--:|--:|:-:|--:|
| 1 | **3,34** | ✅ | 45 s |
| **2** *(actuel)* | **0** | ✅ | 50 s |
| 3 | 0 | ✅ | 90 s |
| 4 | 0 | ✅ | 95 s |

Passer de 1 à 2 supprime **3,34 fausses alarmes par heure pour 5 secondes de latence**. Au-delà,
on paie 40 secondes de plus sans rien gagner. **La valeur retenue est optimale, et c'est maintenant
une mesure, plus une intuition.**

### Mais l'anti-rebond n'existe que pour la déviation

Le banc a révélé une **asymétrie non justifiée** : un ping GPS aberrant à 200 km/h — un seul —
déclenche immédiatement une alerte critique `VITESSE_EXCESSIVE` (1,67 fausse alarme/h dans le
scénario dédié), alors que le même saut appliqué à la position (600 m sur un ping) est correctement
absorbé par l'anti-rebond de la déviation. Les sauts GPS isolés existent ; les bus scolaires à
200 km/h, non.

---

## 5. Le reste des règles tient bien

| Scénario | Attendu | Détecté | Latence | Plancher |
|---|---|:-:|--:|--:|
| trajet normal | rien | ✅ | — | — |
| trajet normal, bruit σ = 15 m | rien | ✅ | — | — |
| arrêts légitimes (1, 2 et 4 min) | rien | ✅ | — | — |
| panne de 8 min | `ARRET_PROLONGE` | ✅ | 305 s | 300 s |
| pointe à 110 km/h | `VITESSE_EXCESSIVE` | ✅ | 0 s | 0 s |
| rue parallèle à 150 m | rien | ✅ | — | — |
| saut GPS isolé de 600 m | rien | ✅ | — | — |

La latence de l'arrêt prolongé (305 s pour un plancher de 300 s) est d'exactement **un ping** :
l'implémentation n'ajoute rien au coût du seuil. Le balayage montre où placer la frontière :

| Seuil | Panne (8 min) détectée | Latence | Fausses alarmes |
|--:|:-:|--:|--:|
| 1 min | ✅ | 65 s | 1 |
| 3 min | ✅ | 185 s | **0** |
| **5 min** *(actuel)* | ✅ | 305 s | 0 |
| 8 min | ❌ | — | 0 |

**3 minutes suffisent** à ne pas confondre un embouteillage de 3 min avec une panne, et font gagner
2 minutes d'alerte. Le choix de 5 min est conservateur — défendable, mais désormais chiffré.

> ⚠️ **Fatigue d'alerte, mesurée** : une seule panne de 8 minutes produit **2 alertes**, parce que
> le `_ALERT_COOLDOWN_S` de 120 s réarme tant que le bus reste immobile. Un incident réel de 30
> minutes en produirait une quinzaine.

---

## 6. Troisième résultat : le classement des détecteurs ML s'inverse

Le benchmark gelé conclut : `iforest_curated` gagne (PR-AUC **0,9127**) devant `seuil_surprise`
(**0,8043**), et la leçon publiée est *« le multivarié gagne, car les anomalies sont hétérogènes »*.

Ce classement repose sur **un seul** bloc de test contenant **8 anomalies**.

### D'abord, l'incertitude

Bootstrap à 2 000 rééchantillonnages sur ce même test :

| Détecteur | PR-AUC | Intervalle de confiance à 95 % |
|---|--:|---|
| iforest_curated | 0,9127 | **[0,722 ; 1,000]** |
| seuil_surprise | 0,8043 | **[0,508 ; 1,000]** |
| seuil_ratio | 0,7934 | [0,503 ; 1,000] |
| iforest_all | 0,4818 | [0,137 ; 0,817] |

Les intervalles des deux premiers **se recouvrent largement**. Publier 0,9127 avec quatre décimales
sur 8 positifs donne une précision que la donnée ne porte pas.

### Ensuite, la validation temporelle glissante

En enchaînant **4 blocs de test successifs** (origine glissante, entraînement toujours sur le passé
seulement), on évalue **38 anomalies** au lieu de 8. Le classement **s'inverse** :

| Détecteur | PR-AUC moyen | Écart-type | P | R | franc | contextuel | surcharge |
|---|--:|--:|--:|--:|--:|--:|--:|
| **seuil_surprise** | **0,926** | 0,077 | **0,86** | **0,84** | 17/17 | **12/14** | 3/7 |
| iforest_curated | 0,847 | 0,097 | 0,75 | 0,71 | 17/17 | 3/14 | **7/7** |
| seuil_ratio | 0,729 | 0,120 | 0,67 | 0,63 | 17/17 | 5/14 | 2/7 |
| iforest_all | 0,408 | 0,064 | 0,39 | 0,37 | 11/17 | 0/14 | 3/7 |

**Un seuil univarié bat le modèle multivarié.**

### Et la thèse publiée est fausse dans le détail

La documentation affirme : *« un seuil univarié attrape surtout les francs ; Isolation Forest
attrape les trois »*. Le tableau dit autre chose, et c'est plus intéressant :

- `seuil_surprise` attrape le **contextuel** bien mieux (**12/14**) que l'Isolation Forest (3/14) —
  ce qui est logique, puisque `surprise` a été **conçue exactement pour ça** : un ratio rapporté aux
  conditions. Le feature engineering fonctionne si bien que le modèle devient superflu ;
- `iforest_curated` est le seul à attraper la **surcharge** (**7/7** contre 3/7) — logique aussi,
  c'est le seul à voir `dwell` et `nb_montees` ;
- aucun ne domine. Ils sont **complémentaires**.

### L'union ne sauve pas la mise — et il fallait le vérifier honnêtement

Unir les deux détecteurs semble évident. Mais une union qui alerte deux fois plus n'a aucun mérite :
la **règle du budget égalisé** s'applique. On calibre donc l'union par dichotomie pour qu'elle émette
**le même nombre d'alertes** qu'un détecteur seul :

| | Alertes | P | R | franc | contextuel | surcharge |
|---|--:|--:|--:|--:|--:|--:|
| seuil_surprise | 37 | **0,86** | **0,84** | 17/17 | **12/14** | 3/7 |
| iforest_curated | 36 | 0,75 | 0,71 | 17/17 | 3/14 | **7/7** |
| union à budget égal | 37 | 0,81 | 0,79 | 17/17 | 7/14 | 6/7 |

L'union est un **compromis**, pas un gagnant : elle récupère la surcharge (6/7) en perdant du
contextuel (7/14). À budget égal, `seuil_surprise` seul reste devant.

---

## 7. La fuite qu'on soupçonnait n'existe pas — et c'est une bonne nouvelle

`features.FT` et `features.FM` reprennent **exactement** les coefficients `F_TRAFIC` / `F_METEO`
du générateur. La variable `surprise` connaîtrait donc le processus qui a fabriqué les données —
un soupçon sérieux de circularité, d'autant plus gênant que `surprise` est le détecteur gagnant.

On l'a testé : les coefficients sont **ré-estimés depuis les seules données d'entraînement de
chaque bloc** (médiane stratifiée du log-ratio, robuste aux 1,25 % d'anomalies), sans jamais
regarder le générateur.

| Catégorie | Générateur | Estimé des données |
|---|--:|--:|
| trafic modéré | 1,15 | 1,07 |
| trafic dense | 1,40 | 1,28 |
| trafic embouteillage | 1,80 | 1,63 |
| météo pluie | 1,20 | 1,10 |
| météo brouillard | 1,15 | 1,00 |

| Détecteur | PR-AUC (codé en dur) | PR-AUC (estimé) | Écart |
|---|--:|--:|--:|
| seuil_surprise | 0,926 | **0,929** | **+0,003** |
| iforest_curated | 0,847 | 0,822 | −0,024 |
| seuil_ratio | 0,729 | 0,729 | +0,000 |

**Le gagnant ne doit rien à la fuite** : il fait même marginalement mieux avec des coefficients
estimés. La structure multiplicative du trafic est **récupérable depuis un historique ordinaire** —
ce qui est précisément ce qu'un exploitant possède. La méthode est donc transposable au terrain.

*(Nuance à ne pas escamoter : les facteurs Ramadan et souk étaient déjà **approximatifs** dans
`features.py` — 1,15 et 1,10 contre 1,25 et 1,12 dans le générateur. La fuite exacte ne portait que
sur le trafic et la météo, et c'est bien ce qui a été testé.)*

---

## 8. Le budget d'alerte, pour l'exploitant

Le benchmark gelé fixe le budget à 1,28 %. La question de l'administration est plutôt *« combien
d'alertes par jour puis-je traiter ? »* :

| Budget | Alertes / 720 trajets | seuil_surprise (P/R) | iforest_curated (P/R) |
|--:|--:|---|---|
| 0,5 % | 4 | 1,00 / 0,50 | 1,00 / 0,50 |
| 1,28 % | 9 | 0,55 / 0,75 | 0,70 / 0,88 |
| 2 % | 14 | 0,40 / 0,75 | 0,53 / **1,00** |
| 5 % | 36 | 0,19 / 0,88 | 0,22 / **1,00** |

À 2 % de budget, `iforest_curated` atteint **100 % de rappel** sur ce bloc. La courbe permet enfin
de discuter le réglage avec l'exploitant plutôt que de le lui imposer.

---

## 9. Verdict

**Ce qui est confirmé**
- Les règles d'arrêt prolongé et de vitesse fonctionnent, sans fausse alarme sur trajet normal,
  avec une latence égale au plancher de leur seuil.
- L'anti-rebond à 2 pings est le bon réglage : −3,34 fausses alarmes/h pour +5 s.
- Le gain de `surprise` sur `ratio` est **réel et transposable** : il ne vient pas d'une fuite.

**Ce qui est infirmé**
- « Le multivarié gagne » : sous validation glissante, **le seuil univarié `surprise` gagne**
  (0,926 vs 0,847). Le classement du benchmark gelé n'était pas stable — 8 positifs ne suffisaient pas.
- « Le seuil rate le contextuel » : c'est **l'inverse** (12/14 contre 3/14). Ce que l'Isolation
  Forest apporte en propre, c'est la **surcharge** (7/7 contre 3/7).

**Ce qui est à corriger**
1. La règle de déviation ignore la progression du bus → aveugle sur 70 % du parcours pour un détour
   de 300 m. Remède connu et déjà éprouvé dans le projet (`depuisAlongM`).
2. `SEUIL_DEVIATION_M` peut descendre de 250 m à ~120 m sans coût mesuré.
3. `VITESSE_EXCESSIVE` mérite le même anti-rebond que la déviation.
4. Le cooldown de 120 s transforme un incident en série d'alertes.

> Aucun de ces correctifs n'a été appliqué : ce document mesure, il ne modifie pas la production.

---

## 10. Reproduire

Aucun service à allumer — tout est hors ligne.

```bash
cd ms11-analytique
python replay.py             # règles live  → data/live_rules_benchmark.json
python ablation_anomaly.py   # détecteur ML → data/ablation_anomaly.json
```

Le rejeu utilise `frontend/chauffeur-mobile/test/fixtures/tournee_groupe1.json` (753 points).
Le bruit GPS est tiré d'une graine fixe : les colonnes d'un même tableau sont comparables entre elles.

## 11. Ce qui reste non vérifié

- **Aucune donnée GPS terrain.** Les traces sont synthétiques, construites sur une géométrie réelle.
  Le bruit gaussien isotrope est une approximation : le vrai bruit urbain est corrélé dans le temps
  et biaisé près des bâtiments. Les seuils recommandés sont donc à confirmer sur un enregistrement réel.
- Le dataset d'anomalies reste **entièrement simulé**, et les natures d'anomalie sont celles que
  nous avons nous-mêmes modélisées.
- L'effectif reste modeste même agrégé : 38 positifs, dont **7 surcharges**. L'écart 7/7 contre 3/7
  repose sur sept cas.
