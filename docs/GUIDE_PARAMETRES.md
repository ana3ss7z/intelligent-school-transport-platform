# Guide des paramètres — page **Réglages**

> **À qui s'adresse ce document ?** À la personne qui administre le système au quotidien.
> Aucune connaissance technique n'est nécessaire. Chaque réglage est expliqué en trois points :
> *à quoi il sert*, *ce qui se passe si on l'augmente ou si on le diminue*, et *quand y toucher*.

**Où :** `http://localhost:5173/settings` — réservé au compte administrateur.

---

## Sommaire

| Onglet | Ce qu'on y règle | Nombre |
|---|---|---|
| [École](#1-école) | Où se trouve l'établissement | 4 |
| [Regroupement](#2-regroupement) | Comment les élèves sont répartis entre les bus | 11 |
| [Tournées](#3-tournées) | Dans quel ordre le bus ramasse les élèves | 1 |
| [Arrivées](#4-arrivées) | Prévision d'arrivée et alerte aux familles | 6 |
| [Contexte](#5-contexte) | Météo et trafic : automatiques ou imposés | 6 |
| [Anomalies](#6-anomalies) | Surveillance des bus pendant le trajet | 6 |
| [Notifications](#7-notifications) | Ce qui est envoyé, et à qui | 6 |
| [Assistant](#8-assistant) | Le robot conversationnel des parents | 13 |
| [Interface](#9-interface) | Vitesse de rafraîchissement des écrans | 7 |

**Total : 60 réglages.**

---

## Comment ça marche

### Enregistrer

Modifiez un ou plusieurs champs, puis cliquez sur **Enregistrer**. Le bouton affiche le nombre de
modifications en attente, et les champs touchés portent une étiquette « non enregistré ».

**Tout est vérifié avant d'être écrit.** Si une seule valeur est refusée — hors des bornes
autorisées, texte à la place d'un nombre — **rien n'est enregistré**, et le message vous dit
exactement laquelle pose problème. C'est voulu : un jeu de seuils appliqué à moitié serait plus
dangereux qu'un enregistrement refusé.

### Quand le changement prend effet

Une étiquette vous le dit sur chaque réglage :

| Étiquette | Signification |
|---|---|
| *(aucune)* | **Immédiat.** Pris en compte dans les secondes qui suivent, sans redémarrer quoi que ce soit. |
| **prochain calcul** | Ne s'applique qu'au prochain lancement du regroupement ou des tournées. |
| **prochain trajet** | Ne s'applique qu'aux trajets démarrés après l'enregistrement. Un bus déjà en route garde ses réglages. |

Le changement se propage à **tout le système** : les services, la console web (côté administration,
chauffeur et parent) et les deux applications mobiles.

### Les champs verrouillés

Certains réglages n'ont de sens que si un autre est positionné d'une certaine façon. Tant que la
condition n'est pas remplie, le champ apparaît **grisé**, avec une étiquette 🔒 **inactif** et une
phrase qui dit exactement quoi changer pour le déverrouiller :

> 🔒 Sans effet tant que « Mode d'approvisionnement du contexte » n'est pas réglé sur `manuel`.

**Cinq champs sont concernés :**

| Champ verrouillé | Se déverrouille quand… |
|---|---|
| Météo imposée | Mode d'approvisionnement = `manuel` |
| Trafic imposé | Mode d'approvisionnement = `manuel` |
| Ramadan | Mode d'approvisionnement = `manuel` |
| Jour de souk | Mode d'approvisionnement = `manuel` |
| Clé API TomTom | Source trafic = `tomtom` |

**Le déverrouillage est immédiat, sans enregistrer.** Passez le mode sur `manuel` : les quatre
champs deviennent modifiables tout de suite. Vous réglez ce que vous voulez, puis vous enregistrez
le tout en une fois.

> **Pourquoi ce verrou ?** Sans lui, on peut renseigner soigneusement « pluie » et « embouteillage »,
> enregistrer, constater que les prévisions n'ont pas bougé — et chercher longtemps pourquoi. La
> raison serait simplement que le mode est resté sur `auto`, donc que le système n'a jamais lu ces
> valeurs. L'écran affichait une chose, le système en appliquait une autre.

**Le verrou est une aide à la saisie, pas une interdiction.** Le serveur accepte toujours d'écrire
ces valeurs — c'est volontaire, pour qu'on puisse préparer un jeu de réglages puis basculer le mode,
ou l'inverse. Si l'ordre des enregistrements devenait significatif, l'aide se transformerait en piège.

> ℹ️ **« Travaux en cours » n'est jamais verrouillé**, et ce n'est pas un oubli : c'est le seul
> réglage de contexte qui agit **dans les deux modes**. Aucune source automatique ne connaît les
> chantiers, donc sans déclaration de votre part le système considère toujours qu'il n'y en a pas.

### Revenir en arrière

Le bouton **Valeurs par défaut** remet l'onglet affiché dans son état d'origine. Les clés d'API
(onglet Assistant) sont **épargnées** : on ne les efface jamais par accident.

Une étiquette **personnalisé** indique un réglage qui a été modifié un jour et diffère encore de sa
valeur d'origine. C'est utile pour retrouver d'un coup d'œil ce qui a été touché.

### Si la page ne s'affiche pas

Le message « le service de configuration est injoignable » signifie que **MS13 n'est pas démarré**.
Ce n'est pas grave : tous les autres écrans continuent de fonctionner normalement, avec les valeurs
par défaut. Il suffit de lancer le service (port 8092) et de recharger.

---

## 1. École

Ces quatre réglages disent au système **où se trouve l'établissement**. Tout en dépend : la
destination des tournées, le calcul des arrivées, la notification « le bus est arrivé », le centre
des cartes, et le contexte donné à l'assistant.

> **Pourquoi c'est important :** avant que ces valeurs ne soient centralisées, elles étaient
> recopiées à six endroits du code — et l'un d'eux se trompait de **900 mètres**. Le message
> « le bus est arrivé à l'école » se déclenchait donc à un endroit qui n'était pas l'école.
> Aujourd'hui il n'existe qu'une seule adresse, et tout le monde la lit.

| Réglage | Valeur d'origine | Limites | À quoi ça sert |
|---|---|---|---|
| **Nom de l'école** | École Al Massira | — | Le nom affiché dans les applications des parents et des chauffeurs. Purement cosmétique. |
| **Latitude** | 33.893 | 27 à 36 | Position nord-sud de l'école. |
| **Longitude** | -5.5455 | -14 à -1 | Position est-ouest de l'école. |
| **Rayon d'arrivée** | 150 m | 20 à 2000 m | Distance en deçà de laquelle on considère que le bus **est arrivé**. |

> Les limites de latitude et de longitude correspondent au territoire marocain : elles empêchent une
> faute de frappe de déplacer l'école à l'autre bout du monde.

**Latitude et longitude.** Ne les modifiez que si l'école déménage, ou si vous constatez que le
point affiché sur la carte est décalé. Pour obtenir les bonnes valeurs : ouvrez Google Maps, faites
un clic droit sur le bâtiment, les deux nombres apparaissent (latitude d'abord, longitude ensuite).

**Rayon d'arrivée.**
- **Plus grand** (par exemple 300 m) : la notification part plus tôt, alors que le bus est encore
  dans le quartier. Utile si le GPS est imprécis dans le secteur.
- **Plus petit** (par exemple 50 m) : la notification est plus juste, mais **risque de ne jamais
  partir** si le GPS dévie de quelques dizaines de mètres au moment de l'arrivée.
- **Quand y toucher :** si des parents signalent que la notification d'arrivée arrive trop tôt
  (diminuez), ou qu'elle n'arrive pas du tout (augmentez).

---

## 2. Regroupement

Cet onglet décide **quel élève monte dans quel bus**. C'est le réglage le plus lourd de conséquences
de toute la page.

> ⚠️ **À lire avant de toucher à la capacité ou au rayon.**
> Ces deux réglages **redistribuent les élèves entre les bus**. D'après les mesures faites sur les
> 300 élèves réels, environ **7 % des enfants changent de bus** lors d'un changement de ce type —
> une vingtaine de familles à prévenir. Un message de confirmation vous le rappelle au moment
> d'enregistrer.
> **Rien ne bouge tant que vous n'avez pas relancé le calcul** depuis la page *Clustering*.

### Les réglages principaux

| Réglage | Valeur d'origine | Limites |
|---|---|---|
| **Capacité d'un bus** | 50 places | 10 à 100 |
| **Rayon maximal élève → bus** | 0 (désactivé) | 0 à 10 000 m |
| **Distance routière** | Activé | — |
| **Distance routière aussi pour le recalcul automatique** | Désactivé | — |
| **Marge d'exploration du nombre de bus** | 3 bus | 0 à 10 |
| **Recalcul automatique sur événement** | Activé | — |

**Capacité d'un bus.** Le nombre de places. Le système en déduit **tout seul** combien de bus sont
nécessaires — vous ne fixez jamais le nombre de bus à la main.
- **Plus grande** : moins de bus, donc moins de chauffeurs, mais des trajets plus longs et des
  groupes plus étalés géographiquement.
- **Plus petite** : plus de bus, des trajets plus courts et plus groupés, mais un coût supérieur.
- *Constaté :* avec 300 élèves, une capacité de 50 donne **7 bus** ; une capacité de 40 en donne **10**.

**Rayon maximal élève → bus.** La distance maximale acceptée entre un élève et le point de
regroupement de son bus. `0` désactive la contrainte.
- **Plus petit** : les groupes sont plus compacts, mais **des élèves se retrouvent sans bus** et
  basculent en ramassage individuel. *Mesuré : à 1500 m, environ 3 élèves ; à 1000 m, environ 40.*
- **Quand y toucher :** si des familles se plaignent de marcher trop loin. Commencez par 1500 m et
  regardez combien d'élèves deviennent isolés avant de descendre plus bas.

**Distance routière.** Activé, le système calcule les distances **par les routes réelles**.
Désactivé, il calcule à vol d'oiseau — plus rapide, mais faux : à vol d'oiseau on sous-estime le
trajet réel de 1,5 à 1,7 fois.
- *Mesuré :* la distance routière ne change presque rien à la qualité apparente des groupes, mais
  fait gagner **1,7 minute de trajet par enfant** (−9,7 %). **Laissez-la activée.**

**Distance routière aussi pour le recalcul automatique.** Quand le regroupement est relancé tout
seul (nouvelle inscription, déménagement, nouveau bus), il utilise par défaut le calcul rapide.
Activez ceci si vous préférez la qualité à la rapidité, au prix d'un calcul plus long.

**Marge d'exploration du nombre de bus.** Combien de scénarios de flotte le système compare avant de
choisir. Laissez à 3 : au-delà, le calcul s'allonge sans gain.

**Recalcul automatique sur événement.** Normalement activé : ajouter un élève relance le
regroupement automatiquement.
- **Désactivez-le pendant une campagne d'inscriptions.** Sinon chaque élève ajouté rejoue le calcul,
  et le nombre de bus peut changer plusieurs fois — déplaçant à chaque fois des enfants dont la
  situation n'a pourtant pas bougé. Réactivez-le une fois les inscriptions terminées, puis lancez
  **un seul** recalcul.
- Le recalcul manuel depuis la page *Clustering* reste disponible.

### Le garde-fou qualité

Ces cinq réglages ne changent **rien** au fonctionnement : ils décident seulement à partir de quand
le système vous **alerte** que la qualité des groupes s'est dégradée. Verdict possible :
`OK`, `DEGRADE`, `CRITIQUE`.

| Réglage | Valeur d'origine | Ce qu'il déclenche |
|---|---|---|
| **Chute relative de qualité tolérée** | 0,15 | Au-delà de 15 % de baisse, verdict `DEGRADE`. |
| **Chute absolue minimale** | 0,05 | Filtre anti-bruit : une baisse n'est retenue que si elle dépasse aussi ce seuil. |
| **Plancher de qualité** | 0,75 | En dessous de 75 % du niveau de référence, verdict `CRITIQUE`. |
| **Étalement toléré** | 0,25 | Si les groupes s'étalent de plus de 25 %, verdict `DEGRADE`. |
| **Élèves isolés tolérés en plus** | 15 | Au-delà de 15 élèves isolés supplémentaires, verdict `DEGRADE`. |

**Quand y toucher :** en principe jamais. **Si vous recevez des alertes en permanence sans qu'aucun
problème réel n'existe**, augmentez légèrement les deux premiers. À l'inverse, si une dégradation
réelle n'a pas été signalée, diminuez-les.

---

## 3. Tournées

Un seul réglage, qui concerne **l'ordre de passage** du bus chez les élèves.

| Réglage | Valeur d'origine | Limites |
|---|---|---|
| **Budget de calcul par tournée** | 5 secondes | 1 à 60 s |

Le temps laissé à l'ordinateur pour chercher le meilleur itinéraire de chaque bus.
- **Plus long** : itinéraire potentiellement meilleur, mais gain très faible au-delà de quelques
  secondes.
- **Plus court** : calcul plus rapide, itinéraire un peu moins bon.
- **Bon à savoir :** les bus sont calculés **en parallèle**. Passer de 5 à 10 secondes n'allonge
  donc pas le calcul total de 7 fois, mais seulement d'environ 5 secondes.
- **Quand y toucher :** si vous ajoutez beaucoup de bus et trouvez les itinéraires perfectibles,
  essayez 10 ou 15 secondes.

---

## 4. Arrivées

Règle **quand les parents sont prévenus** que le bus approche, et d'où viennent les informations de
météo et de trafic.

| Réglage | Valeur d'origine | Limites |
|---|---|---|
| **Seuil d'alerte « arrivée imminente »** | 10 min | 1 à 60 min |
| **Fréquence maximale de recalcul par bus** | 20 s | 5 à 300 s |
| **Délai minimal entre deux alertes d'un même bus** | 1800 s (30 min) | 60 à 7200 s |
| **Source météo** | open-meteo | `open-meteo` ou `off` |
| **Source trafic** | heuristic | `heuristic` ou `tomtom` |
| **Clé API TomTom** | *(vide)* | — |

**Seuil d'alerte.** Dès que le bus est à moins de N minutes de l'école, les parents reçoivent
« le bus arrive dans ~N min ».
- **Plus grand** (20 min) : les parents sont prévenus plus tôt, mais la prévision est moins fiable
  — beaucoup de choses peuvent encore arriver en 20 minutes.
- **Plus petit** (5 min) : prévision plus sûre, mais peu de temps pour se préparer.
- **Quand y toucher :** c'est un arbitrage à discuter avec les familles.

**Fréquence maximale de recalcul.** Le bus envoie sa position toutes les quelques secondes ; sans ce
frein, le système recalculerait une prévision à chaque fois. Laissez tel quel sauf si le serveur
peine.

**Délai minimal entre deux alertes.** Empêche de renotifier les mêmes familles en boucle pendant que
le bus approche. Diminuez-le seulement si les parents se plaignent de ne recevoir qu'une seule
alerte pour la journée entière (matin **et** soir).

**Source météo.**
- `open-meteo` : la météo réelle, gratuite, sans inscription. **Recommandé.**
- `off` : le système utilise la météo *typique* de la saison à Meknès. Utile si l'accès à Internet
  est coupé.

**Source trafic.**
- `heuristic` : le niveau de trafic est déduit de l'heure et du jour (heures de pointe, week-end).
  **C'est ce qui fonctionne aujourd'hui.**
- `tomtom` : prévu pour du trafic en temps réel, **mais l'intégration n'est pas activée** — le
  système retombe sur le mode heuristique. Ne le sélectionnez pas en croyant gagner en précision.

**Clé API TomTom.** Verrouillée tant que la source de trafic n'est pas sur `tomtom`, et de toute
façon inutile tant que cette intégration n'est pas développée.

---

## 5. Contexte

**L'onglet le plus utile pour une démonstration**, et un vrai filet de secours en exploitation.

Normalement, le système va chercher tout seul la météo (sur Internet), le trafic (d'après l'heure),
le ramadan et les jours de souk (dans un calendrier intégré). Cet onglet permet de **prendre la
main** et d'imposer ces valeurs.

| Réglage | Valeur d'origine | Choix possibles |
|---|---|---|
| **Mode d'approvisionnement** | auto | `auto`, `manuel` |
| **Météo imposée** | ensoleillé | ensoleillé, nuageux, pluie, brouillard |
| **Trafic imposé** | fluide | fluide, modéré, dense, embouteillage |
| **Ramadan** | auto | auto, non, oui |
| **Jour de souk** | auto | auto, non, oui |
| **Travaux en cours** | Désactivé | — |

**Mode d'approvisionnement.** C'est l'interrupteur qui commande tout l'onglet.
- `auto` : les sources réelles décident. **C'est le mode normal.** Les quatre champs suivants sont
  alors **verrouillés**, puisque le système ne les lit pas.
- `manuel` : les valeurs ci-dessous s'imposent, quelles que soient les sources réelles. Les champs
  se déverrouillent **immédiatement**, avant même d'enregistrer.

**Trois raisons de passer en manuel :**
1. **La source est injoignable** — pas d'Internet, service météo en panne : vous imposez la
   météo du jour plutôt que de laisser le système deviner.
2. **Vous savez quelque chose que les sources ignorent** — un chantier, un souk exceptionnel, une
   manifestation.
3. **Pour une démonstration** — montrer en direct l'effet du contexte sur les prévisions, sans
   attendre qu'il pleuve.

> **Effet mesuré sur un même trajet :** beau temps + circulation fluide donne **5,15 minutes** ;
> pluie + embouteillage + travaux donne **11,54 minutes**. Soit **2,24 fois plus long**.

**Rien n'est caché.** Quand vous imposez une valeur, la prévision indique que la source est
« manuel (admin) ». Personne ne peut confondre une donnée réelle avec une donnée imposée.

**Ramadan / Jour de souk.** `auto` laisse le calendrier marocain intégré décider. Forcez la valeur
si l'observation lunaire décale le début du ramadan, ou pour un souk exceptionnel.

**Travaux en cours.** Ce réglage est **le seul qui agit aussi en mode automatique**, tout simplement
parce qu'aucune source ne connaît les chantiers : sans déclaration de votre part, le système
considère toujours qu'il n'y en a pas. Activez-le pendant un chantier, **pensez à le désactiver
après**.

> ⚠️ **N'oubliez pas de revenir en `auto`.** En mode manuel, les prévisions restent figées sur ce
> que vous avez déclaré — s'il pleut réellement et que vous avez laissé « ensoleillé », les
> prévisions seront trop optimistes.

---

## 6. Anomalies

Surveille les bus **pendant le trajet** et alerte l'administration en cas de comportement anormal.

| Réglage | Valeur d'origine | Limites | Effet |
|---|---|---|---|
| **Seuil de vitesse anormale** | 90 km/h | 20 à 200 | Alerte au-delà. |
| **Confirmations avant alerte de vitesse** | 1 | 1 à 10 | Anti-fausse-alerte. |
| **Durée d'immobilité avant alerte** | 5 min | 1 à 120 | Alerte « arrêt prolongé ». |
| **Rayon d'immobilité** | 30 m | 5 à 500 | En deçà, le bus est considéré à l'arrêt. |
| **Écart maximal à l'itinéraire** | 250 m | 50 à 3000 | Alerte « déviation ». *(prochain trajet)* |
| **Confirmations avant alerte de déviation** | 2 | 1 à 10 | Anti-fausse-alerte. |

**Seuil de vitesse anormale.** Un bus scolaire en ville ne devrait jamais atteindre 90 km/h.
Baissez-le (par exemple à 70) si vos trajets sont exclusivement urbains.

**Confirmations avant alerte de vitesse.** À `1`, **un seul relevé GPS aberrant suffit** à déclencher
une alerte critique — et le GPS produit régulièrement des valeurs absurdes en sortie de tunnel ou
après une perte de signal.
- **Passez à `2`** pour exiger une confirmation. *Mesure faite sur la surveillance de déviation :
  exiger deux relevés supprime plus de 3 fausses alertes par heure, pour seulement 5 secondes de
  détection en plus.*

**Durée d'immobilité et rayon d'immobilité.** Un bus qui ne bouge pas plus de 5 minutes déclenche une
alerte. Le rayon de 30 m définit ce que « ne pas bouger » veut dire.
- ⚠️ **Le rayon doit rester supérieur à l'imprécision du GPS.** Réglé trop bas (5 m), un bus à
  l'arrêt « bouge » en permanence aux yeux du système, et l'alerte ne se déclenche jamais.
- Augmentez la durée si vos bus stationnent normalement longtemps devant l'école.

**Écart maximal à l'itinéraire.** Distance au-delà de laquelle on considère que le bus s'écarte de sa
tournée prévue.

> **Réglage à revoir — c'est une recommandation appuyée sur une mesure.** À 250 m, un détour n'est
> détecté que sur **9,6 %** du parcours. La raison : une tournée de 50 arrêts repasse plusieurs fois
> dans le même quartier, si bien qu'un bus égaré reste souvent proche d'une *autre* portion de sa
> propre tournée. **À 120 m, la détection double, sans aucune fausse alerte** jusqu'à 30 m
> d'imprécision GPS. Ce changement n'affecte que les trajets démarrés après l'enregistrement.

---

## 7. Notifications

Cinq interrupteurs. Chacun coupe ou rétablit un type de message. Tous sont activés à l'origine.

| Interrupteur | Destinataire | Message |
|---|---|---|
| **Arrivée à l'école** | Parents | « Le bus est arrivé à l'école. » |
| **Montée et dépose** | Le parent concerné | « Votre enfant est bien monté / a été déposé. » |
| **Arrivée imminente** | Parents | « Le bus arrive dans ~N min. » |
| **Qualité de regroupement dégradée** | Administration | Alerte technique sur la qualité des groupes. |
| **Anomalie détectée** | Administration | Vitesse, arrêt prolongé, déviation. |

### Un réglage numérique en plus

| Réglage | Valeur d'origine | Limites |
|---|---|---|
| **Délai minimal entre deux annonces d'arrivée** | 30 min | 0 à 240 min |

Un bus n'est annoncé qu'**au franchissement** du rayon de l'école : le verrou se réarme quand il
s'en éloigne, donc dans le cas normal il n'y a jamais de doublon. Ce délai est un filet
supplémentaire, pour le cas où un bus ferait des allers-retours autour de la limite du rayon —
manœuvre de stationnement, GPS instable — qui produiraient plusieurs annonces.

- **Plus grand** : plus sûr contre les doublons, mais une seconde arrivée réelle dans la
  demi-heure (matin puis midi, par exemple) ne serait pas annoncée.
- **`0`** : filet désactivé, seul le verrou d'entrée de zone agit.

**Quand couper quelque chose :**
- Pendant une **période de test ou une démonstration**, pour éviter d'envoyer de vrais messages aux
  familles.
- Pendant une **panne connue** qui produit des alertes en rafale, le temps de la corriger.
- Si les familles trouvent qu'elles reçoivent **trop de messages** — coupez le type le moins utile
  plutôt que tout.

> ⚠️ Les messages coupés ne sont **pas mis de côté** : ils ne sont simplement pas envoyés.
> Pensez à réactiver l'interrupteur après.

---

## 8. Assistant

Règle le **robot conversationnel** auquel les parents posent leurs questions (« où est le bus ? »,
« mon fils est-il monté ? »).

### Modèles et clés

| Réglage | Valeur d'origine |
|---|---|
| **Fournisseur principal** | groq |
| **Modèle principal** | openai/gpt-oss-120b |
| **Modèle de secours** | openai/gpt-oss-20b |
| **Modèle de dernier recours** | gemini-2.0-flash |
| **Clé API Groq** | *(masquée)* |
| **Clé API Gemini** | *(masquée)* |

Le système essaie les modèles **dans l'ordre** : si le premier est saturé, il passe au deuxième,
puis au troisième.

> ⚠️ **Les modèles d'intelligence artificielle sont retirés du service sans préavis.** C'est déjà
> arrivé deux fois sur ce projet. Le problème est qu'on ne s'en aperçoit pas : tant qu'un modèle de
> la liste répond, l'assistant fonctionne — mais le filet de sécurité, lui, n'existe plus.

**Le bouton « Vérifier », en bas de l'onglet, interroge les fournisseurs et vous dit lesquels de vos
modèles répondent encore.** Utilisez-le **avant chaque démonstration**. Chaque modèle apparaît avec
une coche verte ou un avertissement rouge.

> 💡 **Conseil qui évite le problème :** préférez un nom se terminant par `-latest`
> (`gemini-flash-latest`) à un numéro de version figé (`gemini-2.0-flash`). Un nom en `-latest` suit
> automatiquement les nouvelles générations et ne disparaît pas.
> *La valeur d'origine `gemini-2.0-flash` ne répond effectivement plus.*

**Les clés d'API.** Le champ affiche des points (`••••••4f2a`) et non la clé.
- **Laissez le champ vide pour conserver la clé actuelle.** Enregistrer l'onglet ne l'efface pas.
- Pour la remplacer, collez simplement la nouvelle.
- Ces clés ne sont **jamais** envoyées au navigateur d'un parent ou d'un chauffeur.

### Comportement du robot

| Réglage | Valeur d'origine | Limites | Effet |
|---|---|---|---|
| **Température** | 0,2 | 0 à 2 | Fantaisie des réponses. |
| **Longueur maximale de réponse** | 800 jetons | 100 à 8000 | Taille des réponses. |
| **Recherches maximum par question** | 5 | 1 à 10 | Nombre de consultations autorisées. |
| **Mémoire de conversation** | 6 échanges | 1 à 20 | Ce dont le robot se souvient. |
| **Socle de connaissances école** | Activé | — | Horaires, règlement. |

**Température.** Basse (0,2), le robot répond de façon stable et prévisible. Plus haute, il devient
créatif — **ce qui n'est pas souhaitable ici** : on veut des informations exactes sur un bus
scolaire, pas de la variété. **Laissez à 0,2.**

**Longueur maximale de réponse.**
- ⚠️ Ce budget est **partagé avec la réflexion interne** du robot. Si des réponses se terminent au
  milieu d'une phrase, augmentez à 1200.

**Recherches maximum par question.** Combien de fois le robot peut consulter le système (position du
bus, présence de l'enfant…) pour une seule question. En dessous de 3, il risque de ne pas trouver
la réponse ; au-dessus de 5, il tourne en rond.

**Mémoire de conversation.** Combien d'échanges précédents il garde en tête. Plus haut = il suit
mieux le fil, mais chaque question coûte plus cher.

**Socle de connaissances école.** Activé, on lui fournit les horaires et le règlement vérifiés.
- ⚠️ **Désactivé, il répond aux questions d'école de mémoire — c'est-à-dire qu'il invente.**
  Cette option n'existe que pour mesurer l'écart lors d'une évaluation. **Laissez-la activée.**

### Assistant d'administration

| Réglage | Valeur d'origine | Limites |
|---|---|---|
| **Lignes maximum par requête** | 200 | 10 à 2000 |
| **Durée maximale d'une requête** | 5000 ms (5 s) | 500 à 60000 |

Concernent la page où l'administrateur pose des questions en français sur la base de données.
Augmentez la durée si des questions complexes échouent par dépassement de temps.

---

## 9. Interface

Règle **à quelle fréquence les écrans se mettent à jour**, sur le web comme sur les applications
mobiles.

| Réglage | Valeur d'origine | Limites | Concerne |
|---|---|---|---|
| **Rafraîchissement du trajet** | 15 s | 5 à 300 | Savoir si un trajet est démarré. |
| **Rafraîchissement de l'arrivée** | 30 s | 5 à 600 | Le compte à rebours vu par les familles. |
| **Rafraîchissement de la messagerie** | 15 s | 5 à 300 | Réception des messages. |
| **Rafraîchissement du badge** | 20 s | 5 à 300 | La pastille de messages non lus. |
| **Rafraîchissement des listes** | 10 s | 5 à 300 | Incidents, notifications, trajets en cours. |
| **Zoom initial des cartes** | 13 | 8 à 18 | Niveau de zoom à l'ouverture. |
| **Lignes par page** | 25 | 10 à 200 | Pagination des tableaux. |

**Les cinq premiers.**
- **Plus court** : l'information est plus fraîche, mais le serveur et la batterie des téléphones
  travaillent davantage.
- **Plus long** : moins de charge, mais l'information peut avoir jusqu'à N secondes de retard.

> ⚠️ **Ne descendez pas trop bas.** Le système limite chaque appareil à **20 requêtes par seconde**.
> Un parent a plusieurs écrans qui interrogent en même temps ; avec des intervalles très courts,
> multipliés par le nombre d'utilisateurs, les requêtes commencent à être refusées.
> Le minimum de 5 secondes est imposé automatiquement, même si vous saisissez moins.

**Zoom des cartes.** 13 montre la ville. Plus haut (15-16) = plus rapproché ; plus bas (10-11) =
vue d'ensemble.

**Lignes par page.** Au-delà de 100, les tableaux deviennent lents à afficher.

---

## Situations courantes

| Vous voulez… | Allez dans… | Et faites… |
|---|---|---|
| Corriger la position de l'école sur la carte | École | Modifiez latitude et longitude |
| La notification d'arrivée part trop tôt | École | Réduisez le rayon d'arrivée |
| Réduire le nombre de bus | Regroupement | Augmentez la capacité, **puis relancez le calcul** |
| Des élèves marchent trop loin | Regroupement | Fixez un rayon maximal (essayez 1500 m) |
| Inscrire beaucoup d'élèves d'un coup | Regroupement | **Coupez** le recalcul automatique, inscrivez, réactivez, relancez une fois |
| Prévenir les parents plus tôt | Arrivées | Augmentez le seuil d'alerte |
| Internet est coupé, la météo ne répond plus | Contexte | Passez en `manuel` et déclarez la météo du jour |
| Montrer l'effet de la pluie en démonstration | Contexte | `manuel` + pluie + embouteillage |
| Un chantier ralentit les trajets | Contexte | Activez « Travaux en cours » (**et désactivez après**) |
| Trop de fausses alertes de vitesse | Anomalies | Passez les confirmations à 2 |
| Mieux détecter les détours | Anomalies | Descendez l'écart maximal à 120 m |
| Faire des essais sans déranger les familles | Notifications | Coupez les trois premiers interrupteurs |
| Des annonces d'arrivée en double | Notifications | Augmentez le délai minimal entre deux annonces |
| Préparer une démonstration de l'assistant | Assistant | Cliquez sur **Vérifier** et corrigez les modèles signalés |
| L'assistant ne répond plus | Assistant | **Vérifier** ; si tout est rouge, contrôlez les clés d'API |
| Alléger la charge serveur | Interface | Augmentez les intervalles de rafraîchissement |

---

## Réglages à ne pas modifier sans raison

| Réglage | Pourquoi |
|---|---|
| **Distance routière** (Regroupement) | La désactiver fausse les distances de 1,5 à 1,7 fois. |
| **Température** (Assistant) | Au-delà de 0,2, le robot devient imprévisible sur des informations qui doivent être exactes. |
| **Socle de connaissances** (Assistant) | Désactivé, le robot invente les horaires de l'école. |
| **Les cinq seuils de qualité** (Regroupement) | Ils ne changent rien au fonctionnement, seulement au moment où vous êtes alerté. |
| **Fréquence de recalcul** (Arrivées) | Descendre trop bas surcharge le serveur sans améliorer la prévision. |

---

## Ce que la page ne permet **pas** de régler — et pourquoi

Certains paramètres existent dans le système mais **n'apparaissent pas** ici. C'est délibéré.

**Les paramètres d'entraînement de l'intelligence artificielle** (taille du jeu de données, nombre de
jours simulés, taux d'incidents…). Les modèles sont **figés** : ils ont été entraînés une fois, et
les modifier depuis cette page **n'aurait aucun effet**. Les afficher laisserait croire à un réglage
qui n'en est pas un — l'écran mentirait.

**Les limites de débit de la passerelle.** Elles ne peuvent pas être rechargées sans redémarrage
complet. Les afficher promettrait un effet immédiat qui n'existerait pas.

**Le secret de sécurité et les mots de passe de la base de données.** Les modifier depuis une page
web déconnecterait instantanément tous les utilisateurs et couperait la communication entre les
services.

**Les adresses des services entre eux.** Ce sont des réglages d'installation, pas d'exploitation :
une mauvaise valeur couperait une fonctionnalité entière sans message d'erreur clair.

---

## Questions fréquentes

**Est-ce qu'il faut redémarrer quelque chose après un changement ?**
Non. Sauf mention contraire sur le réglage lui-même, l'effet est immédiat — mesuré à moins de
4 secondes pour atteindre tous les services.

**Est-ce que ça change aussi sur les téléphones des parents et des chauffeurs ?**
Oui, pour les réglages qui les concernent (position de l'école, fréquences de rafraîchissement). Ils
récupèrent la nouvelle valeur au démarrage de l'application. Un écran déjà ouvert garde sa fréquence
jusqu'à ce qu'on y revienne.

**Que se passe-t-il si je me trompe ?**
Les valeurs impossibles sont refusées avec un message. Pour le reste, le bouton **Valeurs par
défaut** remet l'onglet dans son état d'origine.

**Est-ce que quelqu'un d'autre peut voir ou modifier ces réglages ?**
Seul un compte administrateur peut ouvrir cette page et enregistrer. Les parents et les chauffeurs
n'y ont pas accès, et les clés d'API ne quittent jamais le serveur.

**J'ai changé la capacité mais rien ne s'est passé.**
Normal : l'étiquette **prochain calcul** signifie que la nouvelle valeur sera utilisée au prochain
lancement du regroupement. Allez sur la page *Clustering* et lancez le calcul.
