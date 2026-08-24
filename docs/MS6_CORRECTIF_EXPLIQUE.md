# Le correctif MS6, expliqué simplement

> **À quoi sert ce document.** Il explique, sans mots techniques, un problème trouvé dans le
> programme qui répartit les élèves dans les bus, et ce qui a été changé pour le régler.
>
> ✅ **C'est fait (24 août).** Le correctif est écrit, testé (63 tests) et vérifié. Les résultats
> mesurés sont au §5. Ce qu'il reste à faire est au §10.

---

## 1. Le problème, en une phrase

**Le programme qui décide combien de bus il faut ne donne pas toujours la même réponse.**

Avec exactement les mêmes 300 élèves, aux mêmes adresses, il répond parfois **7 bus**, parfois
**8**, parfois **9**.

Nous l'avons lancé 30 fois :

| Réponse du programme | Nombre de fois |
|---|--:|
| 7 bus | 17 fois |
| 8 bus | 2 fois |
| 9 bus | 11 fois |

Rien n'a changé entre ces 30 essais. Ni les élèves, ni les adresses, ni les routes.

---

## 2. Comment est-ce possible ?

Le programme fonctionne ainsi : il essaie plusieurs solutions (6 bus, 7 bus, 8 bus, 9 bus), il
**donne une note à chacune**, et il garde celle qui a la meilleure note.

Le souci vient de la note.

> **Une comparaison simple.** Imaginez une balance qui se trompe de 100 grammes à chaque pesée.
> Vous pesez deux sacs : l'un fait 5,00 kg, l'autre 5,05 kg. Lequel est le plus lourd ?
> La balance vous donnera une réponse différente à chaque fois — non pas parce que les sacs
> changent, mais parce que **l'écart entre eux est plus petit que l'erreur de la balance**.

C'est exactement ce qui se passe ici :

- l'écart de note entre 7 bus, 8 bus et 9 bus est **très petit** ;
- mais la note elle-même **varie un peu** d'un calcul à l'autre.

Le programme croit donc choisir la meilleure solution. En réalité, **il tire au sort**.

### Ce qui fait bouger la note

La note change selon **l'ordre dans lequel les élèves arrivent dans la liste**. Et cet ordre n'est
pas fixe : la base de données renvoie les élèves dans l'ordre où ils sont rangés sur le disque, et
cet ordre change dès qu'on met les données à jour.

Or le programme met justement les données à jour à chaque fois qu'il tourne. **Il change donc
lui-même l'ordre pour la prochaine fois.**

---

## 3. Pourquoi c'est grave

Ce n'est pas juste un chiffre qui bouge sur un écran.

**Quand le nombre de bus change, il faut redistribuer tous les élèves.** Un enfant qui était dans
le bus 3 se retrouve dans le bus 6. Sa famille doit être prévenue. Le chauffeur reçoit une nouvelle
liste. L'heure de passage devant la maison change.

Nous avons mesuré ce qui se passe quand **un seul élève s'inscrit** en cours d'année :

| | Aujourd'hui |
|---|--:|
| Le nombre de bus change… | **9 fois sur 15 inscriptions** |
| À chaque changement, des élèves changent de bus… | **12 à 13 %**, soit **environ 35 enfants** |

**Trente-cinq familles dérangées parce qu'un enfant s'est inscrit.** Et ces trente-cinq enfants
n'ont rien à voir avec le nouvel arrivant : ils habitent parfois à l'autre bout de la ville.

---

## 4. Ce que je vais changer

Deux petites choses, dans un seul fichier (`ms6-clustering/selection.py`). Environ 25 lignes.

### Changement n° 1 — Mesurer plusieurs fois avant de choisir

**Aujourd'hui :** le programme note chaque solution **une seule fois**, puis garde la meilleure note.

**Demain :** il notera chaque solution **plusieurs fois**, et gardera la **note du milieu**.

> Pour reprendre la balance : au lieu de peser une fois, on pèse trois fois et on garde la pesée
> du milieu. Une solution qui a eu de la chance sur un essai ne peut plus gagner.

Et quand deux solutions ont des notes **trop proches pour être départagées**, le programme
choisira **la plus petite flotte**. Un bus de moins, c'est un chauffeur de moins et du carburant
en moins — et comme l'écart de qualité n'est pas mesurable, autant prendre le moins cher.

### Changement n° 2 — Ne pas changer de nombre de bus pour rien

**Aujourd'hui :** dès qu'une autre solution semble un tout petit peu meilleure, le programme
change de nombre de bus.

**Demain :** il gardera le nombre de bus actuel, **sauf** dans deux cas :

1. **les élèves ne rentrent plus** dans les bus actuels (il y a trop de monde) ;
2. **une autre solution est nettement meilleure** — pas juste un peu meilleure.

> C'est le même principe qu'un thermostat : il ne rallume pas le chauffage pour un dixième de
> degré. Il attend un vrai écart. Sinon il passerait son temps à s'allumer et s'éteindre.

---

## 5. Ce que ça donne (mesuré)

Nous avons testé les deux versions en inscrivant des élèves un par un, de 270 à 300 :

| | Aujourd'hui | **Après les 2 changements** |
|---|--:|--:|
| Élèves qui changent de bus, en moyenne | 7,2 % | **2,3 %** |
| Élèves qui changent de bus, cas le plus courant | 6,4 % | **1,0 %** |
| Élèves qui changent de bus, pire cas | 13,3 % | **8,0 %** |
| Nombre de fois où la flotte change | **9** | **2** |

Et sur la question de départ — « le programme donne-t-il toujours la même réponse ? » — nous
avons relancé 15 fois avec des ordres différents :

> **15 fois sur 15, la réponse est : 7 bus.** Le tirage au sort disparaît.

---

## 6. Ce qui ne change pas — et la seule chose qui change

**Ce qui ne change pas**

- **La réponse reste 7 bus.** C'est déjà le nombre que le système produit aujourd'hui.
- **Aucun autre service n'est touché.** Ni la base de données, ni les applications mobiles, ni la
  console web. Tout tient dans le service de répartition.

**Ce qui change, et qu'il faut savoir avant de déployer**

Le programme essaie maintenant **5 répartitions** au lieu d'une, et garde la meilleure. Résultat :
la répartition finale est un peu meilleure qu'avant (note de qualité 0,405 → 0,426), mais **elle
n'est pas identique**.

> **Au premier recalcul, 22 élèves sur 300 (7,3 %) changeront de bus. Une seule fois.**

Ce n'est pas un défaut du correctif, c'est le prix d'une meilleure répartition — et c'est **mesuré**,
pas estimé. Les recalculs suivants ne déplaceront plus qu'environ **1 %** des élèves, contre 6 %
aujourd'hui. Conseil pratique : faire ce premier recalcul à un moment où les familles peuvent être
prévenues, pas un lundi matin.

---

## 7. Ce qui a été vérifié

| Vérification | Résultat |
|---|---|
| Relancer le calcul **30 fois** dans des ordres différents | **7 bus à chaque fois**, et **une seule répartition** — donc strictement reproductible |
| Simulation d'inscriptions (270 → 300 élèves) | Élèves déplacés : **1,0 %** en général (contre 6,4 %), et **le nombre de bus ne change plus jamais** (0 fois, contre 9) |
| Passer par le vrai chemin de données (le service qui fournit les élèves) | Même liste dans l'ordre normal et dans l'ordre inverse → **exactement les mêmes affectations, élève par élève** |
| Tests automatiques | **63 tests**, tous au vert |
| Temps de calcul | environ **1,3 seconde** au lieu de 0,3 — invisible à côté du reste |

---

## 8. Trois idées qui semblaient bonnes et que la mesure a corrigées

Je les note parce que c'est la partie la plus instructive du travail.

### « Prendre la meilleure des 5 répartitions pour comparer »

C'était tentant : on essaie 5 fois, on garde la meilleure, on compare. **Mesuré : c'est pire.**
Le service répondait alors 9 bus dans 14 cas sur 30.

*Pourquoi :* certaines options sont régulières, d'autres très irrégulières. Comparer le **meilleur
essai** de chacune revient à récompenser celle qui varie le plus — elle a plus de chances de sortir
un très bon essai par hasard. On compare donc les options sur leur **résultat typique**, et on ne
garde la meilleure répartition qu'**après** avoir choisi le nombre de bus.

### « Une seule marge de tolérance suffit »

J'utilisais la même marge pour deux questions très différentes :

- « ces deux options sont-elles vraiment différentes ? » → une question de **précision de mesure**,
  très petite ;
- « ce petit gain justifie-t-il de redistribuer toute l'école ? » → une question **de bon sens**,
  bien plus large.

Avec une seule marge, la deuxième protection ne se déclenchait jamais. Ce sont maintenant deux
marges distinctes, et c'est ce qui a fait passer les changements de flotte de 2 à **0**.

### « Repartir des groupes de la veille »

L'idée : ne déplacer que ce qui doit l'être. **Mesuré : légèrement pire** (0,7 à 2,7 % d'élèves
déplacés, contre 0,0 à 1,7 % en repartant de zéro). Les enfants ne changent pas de bus parce que
les groupes dérivent doucement, mais parce que **le nombre de bus change d'un coup**. Abandonné.

---

## 9. En résumé

| | |
|---|---|
| **Le problème** | Le nombre de bus était tiré au sort entre 7, 8 et 9 |
| **La cause** | On comparait des notes dont l'écart est plus petit que leur imprécision |
| **La conséquence** | Environ 35 enfants changeaient de bus quand un seul s'inscrivait |
| **Le correctif** | Trier la liste + mesurer plusieurs fois + ne pas changer la flotte pour rien |
| **L'effet** | 7 bus, toujours · élèves déplacés divisés par 6 · plus aucun changement de flotte |
| **Le coût** | 22 élèves changent de bus **une seule fois**, au premier recalcul |
| **Le travail** | 3 fichiers de logique + 63 tests |

---

## 10. Ce qu'il reste à faire

1. **Redémarrer le service de répartition** pour qu'il charge le nouveau code (il tourne encore
   avec l'ancien).
2. **Lancer un recalcul depuis la console web** — c'est là que les 22 élèves changeront de bus.
3. Surveiller les journaux : le service écrit désormais une ligne quand il **maintient** la flotte
   en place (« Hystérésis : flotte maintenue à k=7 »).

---

*Les mesures détaillées et le protocole complet sont dans
[`MS6_BENCHMARK_DISTANCE.md`](MS6_BENCHMARK_DISTANCE.md), section 5.
Les chiffres bruts sont dans `ms6-clustering/data/sensibilite_ordre.json`,
`ms6-clustering/data/stabilite.json` et `ms6-clustering/data/churn_apres_correctif.json`.*
