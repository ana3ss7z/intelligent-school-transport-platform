# Journal d'exécution des corrections

Suivi du [plan de correction](PLAN_CORRECTIONS.md). Chaque lot est consigné avec sa
**vérification contre la stack réelle**, pas avec l'intention.

---

## Lot 0 — Les deux bloquants ✅ **terminé le 26/08**

### B1 — Auto-promotion ADMIN par `POST /api/auth/register`

`ms7-auth/.../controller/AuthController.java` — le rôle n'est plus lu dans le corps de la
requête : une inscription publique crée **toujours** un `PARENT`. Le champ reste toléré dans
`RegisterRequest` (scripts et front l'envoient encore) mais il est ignoré. La création d'un
CHAUFFEUR ou d'un ADMIN passe par `POST /api/auth/users`, déjà `hasRole('ADMIN')`.

```
POST /api/auth/register {"...","role":"ADMIN"}   →  HTTP 201, rôle attribué = PARENT ✅
```

### B2 — 301 élèves et leurs domiciles GPS servis sans jeton

Nouveau `ms2-eleves/.../controller/InternalEleveController.java` exposant
**`GET /internal/eleves`** — préfixe volontairement **hors** de `/api/eleves/**`, car le
prédicat de la passerelle est `Path=/api/eleves/**` et aurait avalé une route interne placée
sous ce préfixe. `permitAll` dans `SecurityConfig`, puis retrait de la ligne qui ouvrait
`GET /api/eleves`.

**Six consommateurs basculés** : `ms5-planification/ms2_client.py`,
`ms6-clustering/ms2_client.py`, `ms12-prediction/context/roster_ms2.py`,
`generer_comptes.py`, `scripts/recette/config_et_push.py`, `scripts/recette/temps_reel.py`.
`e2e_integration_test.py` passe par la passerelle avec un jeton — inchangé.

```
GET :8082/api/eleves        →  401 ✅   (était 200 + 301 élèves)
GET :8082/internal/eleves   →  200, 300 élèves ✅
GET :8080/internal/eleves   →  404 ✅   (non routée — la protection est le routage)
```

**Non-régression des consommateurs** — vérifiée en réel :

| Service | Appel | Résultat |
|---|---|---|
| MS5 | `POST /api/planification/tournee` | 200 ✅ |
| MS6 | `GET /api/clustering/diagnostics` | 200, 300 élèves ✅ |
| MS12 | `POST /api/eta/predict` | 200, ETA 6,74 min ✅ |

Deux assertions ajoutées à `scripts/recette/contrats.py` (A2bis, A2ter) pour que la
régression soit détectée automatiquement à l'avenir.

---

## Lot 3 — Retour à k=7 bus ✅ **terminé le 26/08**

### Ce que la mesure a montré — et une correction de ma part

J'avais écrit dans le plan que l'observation « un groupe à 9 élèves » n'était pas confirmée.
**C'était faux : ma photo datait d'un run antérieur.** Un clustering avait tourné le 26/08 à
01:28 et produit une partition dégénérée. Mesure au moment de la migration :

| | AVANT (k=9) | APRÈS (k=7) |
|---|---:|---:|
| Nombre de bus | **9** | **7** |
| Plus petit groupe | **9 élèves** | **29 élèves** |
| Plus grand groupe | 47 | 50 |
| Groupes sous-remplis (< 20) | **1** | **0** |
| Remplissage moyen | 33,3 / 50 | **42,9 / 50** |
| Taux de remplissage | **67 %** | **86 %** |
| Silhouette | — | **0,4256** (= l'ancre gelée) |
| Verdict qualité | — | **OK** |

Tailles finales : **50 · 44 · 42 · 37 · 50 · 48 · 29**, toutes ≤ 50 (contrainte respectée).
**Deux bus et deux chauffeurs économisés**, et plus aucun véhicule mobilisé pour neuf enfants.

### Comment

`ms6-clustering/etat.py::charger()` renvoie `None` si la mémoire d'hystérésis est absente →
`k_precedent=None` → `choisir_k` tranche à neuf. Le fichier a été **sauvegardé** puis retiré
(`last_selection.json.bak-avant-migration-k7`), le clustering relancé, puis
`POST /api/planification/tournees?persister=true` pour restaurer l'ordre de passage — sans
quoi le simulateur zigzague **en silence** (piège du 19/08).

Rejouable : `python scripts/recette/migration_k7.py` →
`scripts/recette/resultats/migration_k7.json`.

**Vérifications finales** : `ordrePassage` renseigné sur **300/300** élèves, rangs formant
`1..n` sans trou sur les **7** bus. Second passage du clustering : **churn 0 %** — la
partition est déterministe une fois `k` fixé.

### Coût de la migration

**300/300 élèves changent de `busId`.** C'est inhérent au passage de 9 à 7 bus : toute
l'école est redistribuée. Une partie du chiffre tient à la renumérotation des groupes, mais
l'ordre de grandeur est réel — **c'est précisément ce que l'hystérésis existe pour éviter au
quotidien**, et pourquoi cette migration doit être un acte délibéré, annoncé aux familles,
et non un effet de bord d'une inscription.

### ⚠️ Défaut découvert pendant la migration — le piège n° 20 se réarme

Le premier passage a rendu **DEGRADE**, motif *« compacité max +68 % vs référence
(1669,1 → 2804,1 m) »*. La référence en base avait été écrite par le run à **k=9**.

**`reference_applicable` (`quality.py:75`) vérifie `n_eleves`, `capacity` et `rayon_max_m` —
mais pas le nombre de bus.** Or moins de bus ⇒ groupes plus étalés ⇒ compacité max plus
grande, mécaniquement. Une référence écrite à k=9 juge donc un run à k=7 sur une grandeur
qui n'est pas comparable.

Et comme la référence n'est réécrite **que** sur un verdict OK, le système restait bloqué :
*trop exigeante → DEGRADE → jamais mise à jour → toujours trop exigeante*. C'est exactement
le cliquet du piège n° 20, sur une autre grandeur : le correctif de l'époque plafonne la
**silhouette** à l'ancre, il n'y a pas d'équivalent pour la **compacité**, et `k` n'est pas
dans le contexte.

**Traitement appliqué** : référence périmée sauvegardée
(`quality_baseline.json.bak-perimee-k9`) et retirée, pour la faire ré-amorcer depuis le point
de conception **à k=7**. Verdict repassé à **OK**.

**Correctif de fond à porter** (non fait, à ajouter au registre) : inscrire `k` dans le
contexte de la référence, au même titre que la capacité et le rayon — un changement délibéré
de flotte doit **invalider** la référence, pas déclencher une alarme permanente.

---

## Lot 1 — Harnais de scénarios acteur ↔ acteur ✅ **terminé le 26/08**

Nouveau `scripts/recette/scenarios.py` — **39 assertions**, **six comptes réels** résolus
depuis l'état courant de la base : 1 admin, 2 chauffeurs de bus différents, 3 parents de bus
différents. Chaque interaction est testée sur ses **deux faces** : *l'acteur légitime peut*,
*l'acteur voisin ne peut pas*.

Écrit **avant** toute correction, il est parti **rouge sur 15 assertions** — une par faille
de portée. C'était le contrat : le lot 2 n'a consisté qu'à les faire passer au vert, et la
non-régression est acquise par construction plutôt que vérifiée après coup.

Il couvre au passage deux choses que la recette du 26/08 avait prévues sans les jouer : le
**smoke MS9** (six questions — français, darija, injection de prompt, enfant d'un autre
parent, demande d'écriture, NL2SQL admin) et la **messagerie bidirectionnelle** avec ses
badges lu / non-lu.

> Deux « écarts » du premier passage étaient des bugs du test, pas du service : le compteur
> de non-lus renvoie `{"count": n}` et la réponse de MS9 est dans le champ `reply`. Corrigés.
> **MS9 fonctionnait parfaitement depuis le début** — il appelle les bons outils et refuse ce
> qu'il doit refuser.

---

## Lot 2 — Contrôle de propriété ✅ **terminé le 27/08**

**15 failles fermées**, plus deux incohérences d'autorisation. Le harnais passe de
**18/33 à 39/39**.

### La brique commune

Trois services n'avaient aucun moyen de savoir à qui appartenait un bus ou un élève. Deux
routes internes ont été ajoutées, sur le motif déjà retenu pour MS13 — **la protection est
le fait de ne pas être routé par la passerelle**, pas un rôle :

| Route | Service | Sert à |
|---|---|---|
| `GET /internal/parents/{id}/bus` | MS2 | MS1, MS3, MS10 : les bus des enfants d'un parent |
| `GET /internal/bus/chauffeur/{id}` | MS1 | MS2, MS3, MS10 : les bus d'un chauffeur |

Puis un `PorteeService` par service consommateur (MS1, MS2, MS3, MS10). Duplication assumée,
cohérente avec les autres briques dupliquées du projet (`params.py`, `route_eta`) : `ms-common`
est volontairement **sans dépendance Spring**, un `@Service` ne peut donc pas y vivre.

**Tous échouent fermé** : dépendance injoignable ⇒ refus. Un contrôle de propriété qui
s'ouvre quand sa dépendance tombe ne protège rien — c'est précisément pendant un incident
qu'on veut qu'il tienne.

### Ce qui est corrigé, et vérifié en réel

| # | Ce qui était possible | Maintenant |
|---|---|---|
| P1 | tout compte lisait les enfants de tout parent | **403** |
| P2 | tout parent lisait l'historique GPS de tout élève | routes **supprimées** — aucun client ne les appelait |
| P3 | `/carte` : parent et chauffeur voyaient toute la flotte | **redirigés** |
| P4 | tout chauffeur pointait tout élève → notification au parent d'autrui | **403** |
| P5 | tout chauffeur signalait un incident sur tout bus | **403** |
| P6 | tout parent lisait les incidents de toute la flotte | **403** |
| P7 | tout parent lisait la **polyligne** d'un autre bus (la rue de chaque famille) | **403** |
| P8 | tout parent lisait le trajet actif de tout bus | **403** |
| P9 | un chauffeur démarrait sur le bus d'un collègue | **403** |
| P10 | tout chauffeur lisait les élèves de tout bus | **403** |
| P11 | tout chauffeur obtenait la tournée de tout groupe | **403** |
| P12 | un parent voyait 14 positions GPS | **filtré à ses bus** (1 vu, 0 étranger) |
| P13 | un parent désactivait le jeton d'appareil d'un autre | **403** |
| P15 | l'administration déposait un message chez un parent | **refusé** — le destinataire doit être un chauffeur |
| C1 | l'ADMIN ne pouvait pas clore un trajet ⇒ bus bloqué sans recours | **200** |
| C2 | MS7 renvoyait 401 au lieu de 403 ⇒ le front **déconnectait** | **403** |

Pour P12, le choix a été de **filtrer** plutôt que de refuser : un refus sec casserait la
carte du parent, alors que la vue restreinte à ses bus est simplement la vue juste.

### ⚠️ Deux défauts découverts en corrigeant

**1. `GlobalExceptionHandler` écrasait tout statut HTTP explicite.**
Après le premier déploiement des correctifs, tous les refus sortaient en **400** au lieu de
**403**. Cause : `@ExceptionHandler(RuntimeException.class)` est si large qu'il attrape les
`ResponseStatusException` — dont hérite tout statut choisi par le code. Le refus fonctionnait,
mais le client ne pouvait pas le distinguer d'une requête mal formée. Un
`@ExceptionHandler(ResponseStatusException.class)`, **plus spécifique**, a été ajouté aux
quatre services concernés (MS1, MS2, MS4, MS10).

**2. La collection Newman s'appuyait sur la faille qu'on venait de fermer.**
Elle passait de 87/88 à **57/88**. Motif : ses requêtes 01, 03 et GW-02 créaient leur propre
administrateur et leur propre chauffeur par `POST /api/auth/register` avec `role` dans le
corps — c'est-à-dire qu'**elle exploitait l'escalade de privilège pour se dérouler**.

La collection a été réorientée plutôt que rafistolée :
- l'admin vient désormais du **compte seedé** (`admin@transport.ma`) ;
- le chauffeur est créé par la **voie légitime**, `POST /api/auth/users` avec un jeton ADMIN ;
- les requêtes **01 et GW-02** deviennent des **garde-fous** : elles envoient toujours
  `role: "ADMIN"` et vérifient que le rôle attribué est **PARENT**, en direct et à travers la
  passerelle.

La suite retrouve **88/88** — et teste maintenant le correctif au lieu d'en dépendre.

---

## Lot 4 — Non-régression ✅ **27/08**

| Vérification | Avant correction | Après |
|---|---|---|
| `scripts/recette/scenarios.py` | 18/33 | **39/39** ✅ |
| `scripts/recette/contrats.py` | 60/66 | **67/67** ✅ |
| `scripts\recette\newman.cmd` | 87/88 | **88/88** ✅ |
| `scripts/recette/balayage_front.mjs` | 40/42 | **42/42** ✅ |
| Clustering de production | k=9, un groupe à 9 élèves | **k=7**, min 29, verdict **OK** ✅ |

Les 27 routes de web-admin rendent sans une seule erreur console ni requête réseau en échec,
pour les trois rôles, après une connexion réelle par le formulaire.

---

## Lot 5 — Le défaut que l'audit n'avait pas vu ✅ **terminé le 27/08**

**Trouvé par l'usage, pas par les tests.** Après la migration à k=7, l'écran de clustering
affichait de nouveau **9 groupes, dont un à 9 élèves**. La partition avait été rétablie.

### Deux chemins de calcul, deux algorithmes

| Chemin | Déclenché par | Distance utilisée |
|---|---|---|
| **Manuel** — `POST /api/clustering/production` | l'administrateur, depuis l'écran | **routière OSRM** — celle du mémoire, celle qui a été benchmarkée |
| **Automatique** — consumer RabbitMQ | `eleve.created` · `eleve.deleted` · `eleve.gps.updated` · `bus.created` · `bus.deleted` | **euclidienne** (`use_road_for_auto = false`) |

Le recalcul automatique était **actif** et **repartitionnait les 300 élèves** à chaque
événement, avec l'algorithme dégradé. Il réécrivait au passage `last_selection.json`
(la mémoire d'hystérésis) et `quality_baseline.json` (la référence qualité).

**Ce qui l'a déclenché** : Newman crée puis supprime un élève à chaque exécution — jouée
trois fois ce jour-là. Plus le test e2e. Plus la suppression manuelle d'un élève de test par
l'utilisateur. Chacune a effacé la partition routière.

> **Cela explique une anomalie ancienne du projet** : `production_config.json` annonce
> **k=7 routier**, et la production dérivait systématiquement vers **k=9**. C'est le piège
> n° 16 — *« ce qui tourne en production n'est pas ce qui a été benchmarké »* — dans sa
> version la plus profonde : les deux algorithmes coexistaient, et le moins bon écrasait
> l'autre à la première inscription venue.

### Correction

Le drapeau est aligné à trois endroits, parce que chacun peut annuler les autres :
`ms6-clustering/config.py` (le défaut du code), `ms6-clustering/.env` (l'amorçage), et
**MS13** (`ms6.use_road_for_auto`, qui a la priorité) — propagé à chaud, sans redémarrage.

### Vérification — le point important

La question n'était pas seulement « la partition tient-elle ? », mais **« la fonctionnalité
survit-elle ? »**. Le déclencheur « ajout d'élève → recalcul » est une capacité annoncée du
projet (sprint S8) : la couper aurait retiré une démonstration.

| Test | Résultat |
|---|---|
| Recalcul auto **coupé** · élève créé puis supprimé | k=7, churn **0 %** |
| Recalcul auto **réactivé** avec le bon algorithme · élève créé puis supprimé | k=7, churn **0 %**, partition **identique au caractère près** |
| **Newman rejoué en entier** (le coupable d'origine) | **88/88**, partition k=7 intacte, verdict **OK** |

**Le recalcul automatique reste donc activé** : il se déclenche, il utilise désormais le même
algorithme que le calcul manuel, et il ne déplace plus personne. La fonctionnalité est
préservée *et* la partition est stable — on n'a pas eu à choisir.

### Ce que cet épisode enseigne

L'audit du 26/08 avait exercé le calcul manuel et l'avait trouvé correct. Il n'avait jamais
exercé **le chemin automatique**, parce qu'aucun test ne créait puis supprimait un élève en
observant la partition. C'est l'utilisateur qui l'a révélé, en cliquant simplement sur son
propre écran.

---

## Lot 6 — Vérification complète : acteurs, interfaces, briques IA ✅ **27/08**

Trois questions, trois harnais. Deux d'entre eux n'existaient pas.

### Ce qui a été ajouté

| Harnais | Question à laquelle il répond | Assertions |
|---|---|---|
| `scripts/recette/ia.py` **(nouveau)** | Les 5 briques IA donnent-elles des résultats **justes** ? | **35** |
| `scripts/recette/donnees_front.mjs` **(nouveau)** | Les interfaces affichent-elles les **bonnes valeurs** ? | **17** |
| `scripts/recette/scenarios.py` | Un acteur peut-il agir sur les données d'un autre ? | 39 |

`ia.py` ne vérifie pas que les services répondent — `contrats.py` le fait déjà. Il vérifie
que ce qu'ils répondent est **correct** : contraintes métier tenues, grandeurs cohérentes
entre elles, propriétés que les modèles garantissent, déterminisme.

`donnees_front.mjs` complète `balayage_front.mjs` de la même façon : celui-ci prouve que les
27 routes se rendent sans erreur, celui-là lit la vérité dans l'API puis **compare au texte
réellement affiché**. Une page peut se rendre parfaitement et montrer un chiffre faux.

### Résultat d'ensemble

| Harnais | Résultat |
|---|---|
| Scénarios acteur ↔ acteur | **39/39** ✅ |
| Contrats HTTP & RBAC | **67/67** ✅ |
| Justesse des briques IA | **35/35** ✅ |
| Valeurs affichées dans les interfaces | **17/17** ✅ |
| Rendu des 27 routes × 3 rôles | **42/42** ✅ |
| Newman (API + passerelle) | **88/88** ✅ |
| MS13 configuration à chaud & MS4 push | **13/13** ✅ |
| Chaîne temps réel | **11/12** ⚠️ (files orphelines, dette du lot 5) |
| Intégration e2e | **11/12** ⚠️ (G1, seuil non déterministe — piège n° 31) |

**323 assertions, 2 écarts**, tous deux connus et documentés.

### Ce que la vérification des briques IA établit

- **MS6** — capacité jamais dépassée (max 50/50), aucun élève orphelin, aucun élève groupé
  sans bus, k=7 conforme au gel, silhouette au-dessus du plancher, verdict **OK**, et
  **déterminisme** : relancer le calcul ne déplace personne.
- **MS5** — chaque tournée est une **permutation exacte** des élèves du groupe (aucun oublié,
  aucun compté deux fois), convergence distance annoncée ↔ géométrie dessinée à
  **0,03 – 0,08 %**, vitesses plausibles (28 km/h), gain moyen **13,3 %** sur l'ordre naïf, et
  le soir reprend bien le **même ordre** que le matin.
- **MS12** — la garde anti-extrapolation bascule au bon endroit (2 214 m → `modele_direct`,
  11 348 m → `facteur_contexte`), les durées sont **monotones** avec la distance, l'intervalle
  encadre la prédiction, et le contexte a un effet réel : **×2,43** entre beau/fluide et
  pluie/embouteillage sur le **même** tronçon.
- **MS11** — détecteur et métriques conformes au gel (PR-AUC 0,9127), scan à précision 0,696 /
  rappel 0,722, seuils publiés, **détection réelle** d'une vitesse injectée, et l'**anti-spam**
  fonctionne (un second excès dans la minute ne réalerte pas).
- **MS9** — cascade réellement servie par les fournisseurs, et surtout : le NL2SQL renvoie
  **le vrai chiffre** de la base (300 élèves), pas seulement du SQL bien formé.

### Ce que la vérification des interfaces établit

Chaque écran est confronté à la vérité de l'API : le nombre de groupes et **la taille de
chacun** sur `/clustering`, l'effectif sur `/eleves`, les 10 matricules sur `/bus`, le total
des notifications (qui doit venir de `/stats`, pas d'un comptage de la page). Côté chauffeur,
son bus, ses 50 élèves, et **aucun élève d'un autre bus**. Côté parent, ses enfants nommés,
**aucun enfant d'une autre famille parmi les 300**, et seul le bus de son enfant.

---

## ⚠️ Le défaut trouvé pendant cette vérification — la surveillance était morte

**`ms11.gps.queue` : 0 consommateur.** MS11 répondait « UP », `/live` renvoyait
`200 {"n": 0}` — indiscernable de « rien à signaler ». En réalité **plus aucune anomalie
n'était détectée** : ni vitesse, ni arrêt prolongé, ni déviation. Depuis un redémarrage.

Deux causes, toutes deux corrigées dans **MS11, MS12 et MS6** :

1. **`asyncio.create_task()` sans conserver de référence.** La documentation Python demande
   explicitement de stocker le résultat « pour éviter qu'une tâche disparaisse en cours
   d'exécution » : le ramasse-miettes collectait le consumer avant son premier pas. Symptôme
   caractéristique : `tentatives: 0` — la boucle n'avait même pas essayé.
2. **Aucune reprise sur échec de connexion.** `connect_robust` reconnecte une connexion
   **déjà établie**, mais ne fait rien si la première tentative échoue — et les 13 services
   démarrent ensemble. L'ancienne version attrapait l'exception, écrivait une ligne de
   journal, et laissait le service tourner sans consumer, définitivement.

**Rendu observable** : `GET /api/analytique/health` publie désormais `surveillance_live`
(connecté, tentatives, dernière erreur, depuis quand) et `/live` publie
`surveillance_active`. Un tampon vide ne peut plus se confondre avec un service qui n'écoute
plus.

**Vérifié après correctif** : les deux files de MS11 ont leur consommateur, une vitesse
injectée est détectée, et une déviation de 6 074 m est levée contre un seuil de 250 m.

### Trois artefacts de test corrigés au passage

Ils échouaient sans qu'aucun défaut n'existe — et chacun apprend quelque chose sur le système :

- **Le premier ping d'un bus n'est jamais analysé.** `observer()` retourne tôt faute de
  position précédente : on ne dérive pas une vitesse d'un seul point. Les tests amorcent
  désormais avant de mesurer.
- **Une alerte par type et par bus toutes les 2 minutes** (`_ALERT_COOLDOWN_S`). Réutiliser
  un bus déjà alerté ne prouve rien. Le test choisit maintenant un bus « frais » — et vérifie
  l'anti-spam comme une fonctionnalité à part entière.
- **Le e2e lisait le journal d'administration paginé** (25 lignes) pour y chercher la
  notification d'un parent. Le système en produit assez pour l'enterrer en quelques secondes.
  Il lit désormais avec le jeton du parent — la lecture que fait la vraie application.

---

## Reste ouvert — dette assumée et documentée

| # | Défaut | Décision |
|---|---|---|
| **P14** | **WebSocket GPS sans authentification** — aucun jeton, origine `*`, filtre « tout » par défaut | **différé** : touche les 3 frontends d'un coup, risque avant soutenance. Solution décrite dans le plan |
| — | `quality_baseline.json` : le contexte ne porte pas `k` | à corriger — un changement de flotte doit invalider la référence, pas déclencher une alarme permanente |
| Lot 5 | 5 `pom.xml` à `skipTests=true` · 7 files RabbitMQ orphelines (28 944 messages) · fichiers Firebase orphelins · scripts qui ne démarrent pas sur console Windows | non fait |
| Lot 6 | bornes du domaine d'entraînement MS12 · référence qualité plafonnée à l'affichage · colonne « Public » des tableaux d'endpoints · actuator de la passerelle | non fait |
| — | Règle de déviation : 16 à 29 % de couverture à 300 m | chantier à part entière |

Zones jamais couvertes, inchangées : **aucune intégration continue**, **aucun téléphone
physique**, **aucune cible iOS**, **le canal push n'a jamais délivré un message réel**, et
**les ports de service ne sont pas isolés** — c'est la vraie réponse de fond à la famille B2.

