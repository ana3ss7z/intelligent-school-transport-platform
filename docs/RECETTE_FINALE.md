# Recette finale — Transport Scolaire Intelligent

**Date d'exécution : 26 août 2026.** Stack complète en fonctionnement (13 microservices,
OSRM, PostgreSQL/Redis/RabbitMQ, web-admin), 301 élèves en base, 10 bus, 216 parents.

Ce document est la **vérification de bout en bout** du projet avant rédaction du mémoire.
Son objet n'est pas de montrer que tout marche, mais de **confronter chaque chiffre publié
dans `README.md` et `CLAUDE.md` à ce que la stack fait réellement aujourd'hui** — et de
chiffrer les écarts. Tous les scripts sont rejouables : `scripts/recette/`.

---

## 1. Résultat d'ensemble

| Phase | Objet | Score | Détail |
|---|---|---|---|
| 1 | Suites hors ligne (unitaires, analyse statique, build) | **voir §2** | écarts sur les chiffres publiés |
| 2 | Contrats HTTP & RBAC contre la passerelle vivante | **60/66** | 6 écarts, tous réels |
| 3 | Newman (collection v4) | **87/88** | l'assertion cassée est une assertion de sécurité |
| 4 | `e2e_integration_test.py` | **11/12** | G1 échoue de 3,6 s sur un seuil |
| 5 | Chaîne temps réel (trajet, anomalies, incidents) | **10/12** | 2 écarts réels |
| 6 | Les 5 briques IA contre la stack réelle | **conforme** | MS5, MS9, MS11, MS12 confirmés ; MS6 à nuancer |
| 7 | MS13 (config à chaud) & MS4 (canal push) | **13/13** | tous les correctifs des pièges 21/23/24 tiennent |
| 8 | 27 routes web-admin dans un vrai Chrome | **40/42** | 0 erreur console ; 2 écarts RBAC |

**20 défauts trouvés**, dont **2 critiques** et **3 élevés**. Aucun n'a été corrigé :
conformément à la discipline de la campagne de benchmark du 23/08, les défauts sont
**rapportés, chiffrés et documentés**, la correction étant une décision de production.

---

## 2. Phase 1 — suites hors ligne

| Cible | Publié | Obtenu | Verdict |
|---|---|---|---|
| `pytest ms6-clustering/tests` | 75 | **75 ✅** | ⚠️ ne passe **que** depuis `ms6-clustering/` (défaut n° 14) |
| `pytest ms9-llm/tests` | 36 | **36 ✅** | conforme |
| `ms9-llm/eval/rapport_sql_guard.py` | 14/14 · 8/8 | **29 cas, 0 écart, exit 0** | conforme |
| `mvn test` (9 modules) | 22 méthodes | **18** (MS4 17 + MS10 1) | ❌ **5 modules ne testent rien** (défaut n° 6) |
| `flutter test` chauffeur | 93 | **93 ✅** | conforme |
| `flutter analyze` chauffeur | 0 issue | **5 erreurs** | ❌ défaut n° 15 |
| `flutter test` parent | 38 | **38 ✅** | conforme |
| `flutter analyze` parent | 0 issue | **3 infos** | ⚠️ défaut n° 15 |
| `bun run build` web-admin | ✅ | **✅** | conforme |
| `bun run lint` web-admin | — | **16 avertissements, 0 erreur** | conforme |

---

## 3. Défauts trouvés, par gravité

### 🔴 CRITIQUE 1 — N'importe qui devient administrateur en une requête

`POST /api/auth/register` est `permitAll` **et lit le champ `role` dans le corps de la
requête**. Une seule requête non authentifiée suffit :

```bash
curl -X POST http://localhost:8080/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"nom":"Intrus","email":"x@evil.test","motDePasse":"X123!","role":"ADMIN"}'
# → HTTP 201 + un jeton dont le rôle est ADMIN
```

**L'escalade est pleinement exploitable — vérifié, 6 surfaces sur 6 ouvertes** :

| Surface ouverte au compte auto-promu | Ce qu'elle expose |
|---|---|
| `GET /api/auth/users` | tous les comptes de la plateforme |
| `GET /api/eleves` | 301 élèves, nom, prénom, **domicile GPS**, parent |
| `GET /api/notifications` | journal complet des notifications |
| `GET /api/parametres/schema` | toute la configuration métier (MS13) |
| `POST /api/llm/admin/query` | **NL2SQL : requêtes libres sur la base** |
| `GET /api/trajets/actifs` | position opérationnelle de toute la flotte |

La défense en profondeur de MS9 (rôle `ms9_readonly`, transaction `READ ONLY`) tient
toujours, mais elle protège de l'écriture, pas de la lecture — et c'est bien la lecture
qui est en jeu ici.

> **Correction attendue** : ignorer `role` dans `/register` (forcer `PARENT`), et réserver
> la création de comptes privilégiés à `POST /api/auth/users`, déjà protégé par `hasRole('ADMIN')`.

### 🔴 CRITIQUE 2 — 301 élèves et leurs domiciles GPS, sans aucune authentification

`GET /api/eleves` est déclaré `permitAll` dans `ms2-eleves/.../SecurityConfig.java`.
Sur le port du service, **aucun jeton n'est requis** :

```bash
curl http://localhost:8082/api/eleves   # → HTTP 200, 301 élèves
# {"id":38,"nom":"Amrani","prenom":"Houda","latitude":33.901829,"longitude":-5.545362,
#  "parentId":420,"groupeId":2,"busId":15,"statutPresence":true,"ordrePassage":11}
```

C'est le jeu de données le plus sensible du projet : **identité et adresse de 301 enfants**.

**Ce défaut était déjà détecté — par l'assertion Newman n° 13, jamais rejouée.**
C'est ce qui fait passer la collection de 88/88 à **87/88**. La route a probablement été
ouverte parce que MS5 lit les élèves sans jeton utilisateur (« MS5 n'a pas de token
utilisateur », `CLAUDE.md`). Le besoin est réel ; la solution retenue expose tout.

> Nuance à défendre : la passerelle, elle, exige un JWT (vérifié : 401). Le projet traite
> les ports de service comme privés. Mais rien ne les isole — pas de réseau Docker pour les
> applications, tous les services écoutent sur `localhost` de la même machine.

### 🟠 ÉLEVÉ 3 — Aucun contrôle de propriété sur trois routes

Un parent authentifié lit les données d'une autre famille :

| Route | Résultat mesuré |
|---|---|
| `GET /api/eleves/parent/{autre_parentId}` | **HTTP 200** + la fratrie d'autrui |
| `GET /api/gps/eleve/{eleveId}/historique` | **HTTP 200** pour l'enfant d'un tiers |
| `GET /api/gps/eleve/{eleveId}/derniere` | 404 ici (pas de données), mais non gardée |

Le JWT porte `userId` ; aucune de ces routes ne le compare au `parentId` demandé.
C'est d'autant plus notable que MS5 et MS9 font **exactement** ce contrôle
(`/api/planification/mes-enfants` prend la portée dans le jeton, jamais dans la requête) —
le motif correct existe dans le projet, il n'a pas été appliqué partout.

### 🟠 ÉLEVÉ 4 — `/carte` n'a aucun garde de rôle

`frontend/web-admin/src/App.tsx:63` déclare `/carte` sans `roles`. Vérifié dans Chrome :
un **PARENT** et un **CHAUFFEUR** qui saisissent l'URL obtiennent la carte live complète.

Mesuré pour un parent d'**un seul** enfant (`karim.alaoui.50@famille.ma`) :
**14 positions GPS de bus en direct** et **les 10 bus de la flotte** (matricule, capacité,
chauffeur). Les 13 autres routes protégées redirigent correctement — c'est la seule fuite.

### 🟠 ÉLEVÉ 5 — Un administrateur ne peut pas clore un trajet

`POST /api/trajets/{id}/terminer` est annoté `hasAnyRole('CHAUFFEUR','ADMIN')`, mais le
service vérifie ensuite la propriété :

```
ADMIN     → HTTP 400  « Ce trajet n'appartient pas à ce chauffeur. »
CHAUFFEUR → HTTP 200  (le propriétaire)
```

L'autorisation accordée à l'ADMIN est donc **creuse**. Conséquence opérationnelle : si le
téléphone du chauffeur tombe en panne, s'il perd l'application ou quitte son service, le
trajet reste `EN_COURS` indéfiniment. Or le démarrage est **non idempotent** (vérifié :
`400 « Un trajet est déjà en cours »`) : **le bus est bloqué, sans aucun recours par l'API**.
Rencontré pour de vrai pendant cette recette — le trajet #21 a dû être clos avec le jeton
du chauffeur.

### 🟡 MOYEN 6 — `mvn test` est vert en ne testant presque rien

Cinq `pom.xml` portent `<skipTests>true</skipTests>` : **ms1-bus, ms2-eleves,
ms3-localisation, ms7-auth, ms8-gateway**. La sortie Maven dit `Tests are skipped.` puis
`BUILD SUCCESS`. Le total réel est **18 tests** (MS4 17, MS10 1), pas 22.

Autrement dit : les quatre modules qui portent l'**authentification**, la **passerelle**,
les **élèves** et les **bus** n'exécutent aucun test, et rien ne le signale. C'est la même
famille que le piège n° 23 : *un signal toujours vert vaut absence de signal*.

### 🟡 MOYEN 7 — 28 944 messages dans 7 files RabbitMQ sans consommateur

| File | Messages | Consommateurs |
|---|--:|--:|
| `gps.bus.updated.queue` | **28 918** | **0** |
| `incident.signale.queue` | 10 | 0 |
| `incident.resolu.queue` | 8 | 0 |
| `eleve.created.queue` | 4 | 0 |
| `eleve.deleted.queue` | 3 | 0 |
| `eleve.gps.updated.queue` | 1 | 0 |
| `gps.eleve.updated.queue` | 0 | 0 |

MS2, MS3 et MS10 **déclarent et lient** ces files sans jamais les consommer : les vrais
consommateurs (MS4, MS6, MS11, MS12) ont leurs propres files. Chaque ping GPS ajoute donc
un message qui ne sera jamais lu. Croissance non bornée du disque du broker.

*Point positif vérifié* : les **18 files fonctionnelles ont toutes leur consommateur**, y
compris les 5 files exclusives `parametres.updated` (une par service Python, conformément
au piège n° 22).

### 🟡 MOYEN 8 — MS7 déguise un refus d'autorisation en échec d'authentification

Un CHAUFFEUR ou un PARENT qui appelle `/api/auth/users` reçoit **401 `{"error":"Token
invalide"}`** au lieu de **403**. Le jeton est pourtant valide — `GET /api/auth/validate`
avec le même jeton renvoie `200 « Token valide — chauffeur1@transport.ma [CHAUFFEUR] »`.

Cause : `ms7-auth/.../SecurityConfig.java` définit un `authenticationEntryPoint` mais
**aucun `accessDeniedHandler`** (seul service Java dans ce cas). Tous les autres renvoient
bien 403 — vérifié sur 22 combinaisons rôle × route.

**Conséquence visible pour l'utilisateur** : `frontend/web-admin/src/api/client.ts`
traite tout 401 comme une session expirée et **déconnecte**. Un chauffeur qui atteint une
route d'administration est donc éjecté de la console au lieu de voir un refus.

### 🟡 MOYEN 9 — La règle de déviation est plus aveugle que documenté

Mesuré sur **deux vraies tournées**, en appliquant un détour de *D* mètres en 40 points
répartis, dans 8 directions, puis en mesurant la grandeur que MS11 compare au seuil de 250 m
(distance au point le plus proche de **toute** la polyligne) :

| Détour réel | Groupe 1 (9,4 km) détecté | Groupe 3 (17,2 km) détecté |
|---:|---:|---:|
| 100 m | **0,0 %** | **0,0 %** |
| 150 m | 0,0 % | 0,0 % |
| 200 m | 0,0 % | 0,0 % |
| 250 m | 0,0 % | 0,0 % |
| 300 m | 29,1 % | 16,3 % |
| 400 m | 50,9 % | 33,7 % |
| 600 m | 65,7 % | 55,2 % |
| 800 m | 75,9 % | 66,3 % |
| 1 200 m | 86,6 % | 80,2 % |

Deux enseignements, dont un **nouveau** par rapport au piège n° 17 :
1. Même un détour de **1 200 m** passe inaperçu sur 13 à 20 % du parcours.
2. **Plus la tournée est longue, plus la règle est aveugle** : le groupe 3 (17,2 km) est
   systématiquement moins bien couvert que le groupe 1 (9,4 km), à détour égal. La règle se
   dégrade donc précisément là où le risque est le plus grand.

La détection **fonctionne** quand elle se déclenche : écarts mesurés de **975,9 m** et
**595,8 m** contre le seuil de 250 m, avec l'anti-rebond à 2 pings.
⚠️ Une exécution sur trois n'a rien déclenché avec le même protocole — **intermittence non
expliquée**, à investiguer.

### 🟡 MOYEN 10 — La production tourne à k=9 bus, la documentation annonce k=7

`ms6-clustering/data/last_selection.json` porte `k: 9`. `production_config.json` annonce
`k_production: 7`. Le clustering appliqué pendant la recette a produit **9 groupes**
(tailles 37, 40, 31, 28, 49, 30, 32, 26, 28 — toutes ≤ 50, contrainte respectée).

**Ce n'est pas un défaut de l'algorithme : c'est l'hystérésis qui fait son travail.**
Churn mesuré avant/après application : **0/301 élèves ont changé de bus (0,0 %)**, contre
7,3 % attendus au premier recalcul. Le correctif du piège n° 19 est donc **confirmé en
production**, et de la meilleure façon possible.

Mais l'hystérésis ancre le système sur une partition à 9 bus **antérieure au correctif**.
Le k=7 documenté ne sera jamais atteint sans effacer `last_selection.json`. **Deux bus et
deux chauffeurs d'écart entre le mémoire et la réalité** — à trancher avant la soutenance :
soit on réinitialise, soit on publie k=9 en expliquant pourquoi.

Le garde-fou qualité rend `OK` (silhouette 0,681, compacité max 993 m, faisable).

### 🟡 MOYEN 11 — La garde anti-extrapolation de MS12 ne tient qu'au fichier CSV

`ms12-prediction/data/eta_config.json` porte `"domaine_entrainement": null`. La garde
fonctionne quand même parce que `model.py:36` retombe sur le dataset :

```python
self.domaine = self.config.get("domaine_entrainement") or self._domaine_depuis_dataset()
```

Bornes effectivement en vigueur, recalculées depuis `eta_dataset.csv` (0,5 Mo) :
`distance 694–3 995 m` (médiane 2 695), `durée 100–353 s` (médiane 250).

**La garde est vérifiée en fonctionnement** : à 2 214 m / 272 s → `modele_direct` ;
à 3 595 m / 388 s → `facteur_contexte` (déclenché par la **durée**, 388 s > 353 s).

Mais déployer le service avec le seul artefact gelé — ce qui est la façon normale
d'expédier un modèle — ferait renvoyer `{}` à `_domaine_depuis_dataset()`, donc
`dist_max = None`, donc `hors_domaine = False` **toujours** : le modèle extrapolerait sur
des tournées de 12 km, **sans le moindre message**. Le CSV de 0,5 Mo est une dépendance de
production non déclarée.

### 🟡 MOYEN 12 — Le test G1 du e2e est non déterministe par construction

`e2e_integration_test.py` pousse une position à `(33.905, -5.575)` et attend une
notification `BUS_EN_ROUTE`, publiée si l'ETA ≤ `ETA_ALERT_MIN` = 10 min.

**ETA mesurée ce jour : 10,06 min.** Le test échoue de **3,6 secondes**.

La position est à 3 595 m de l'école, durée OSRM de base 6,47 min ; le contexte du jour
(nuageux, trafic dense, jour de souk) l'a portée à 10,06. Par temps clair et trafic fluide,
la même position passe. Le « 8/8 » historique tenait au calendrier.

**La chaîne, elle, est intacte — prouvée séparément** : une position à 2 214 m (ETA
6,74 min) produit la notification `BUS_EN_ROUTE` en **3 secondes**
(*« Le bus de votre enfant arrivera à l'école dans ~5 min »*). MS3 → MS12 → RabbitMQ → MS4
fonctionne de bout en bout.

> Correction : figer le contexte du test (`auto_context=false`) ou choisir une position
> avec de la marge. Un test dont le résultat dépend de la météo n'est pas un test.

### 🔵 FAIBLE 13 à 20

| # | Défaut | Mesure |
|---|---|---|
| 13 | `e2e_integration_test.py` **ne démarre pas** sur une console Windows par défaut | `UnicodeEncodeError` sur le premier emoji (cp1252). Contournement : `PYTHONIOENCODING=utf-8`. Un lecteur qui reproduit le « 8/8 » échoue à la première ligne. |
| 14 | `pytest ms6-clustering/tests` échoue **depuis la racine** | Le `.env` racine (POSTGRES_*, MS1_PORT…) est chargé par pydantic-settings, qui interdit les champs surnuméraires → 2 erreurs de collecte. Or c'est la commande que prescrivent les docstrings. |
| 15 | `flutter analyze` n'est pas à 0 | Chauffeur : **5 erreurs**, toutes dans `lib/firebase_options.dart` — fichier orphelin (Firebase n'est pas une dépendance de cette app et n'est jamais initialisé). Parent : 3 `info` (`unnecessary_underscores` dans les tests). |
| 16 | Les endpoints « Public » ne le sont pas via la passerelle | 6 vérifiés (`/clustering/health`, `/eta/health`, `/analytique/live`, `/planification/health`, `/llm/health`, `/clustering/quality`) : **200 en direct, 401 via :8080**. La colonne « Public » des tableaux du `CLAUDE.md` n'est vraie que sur le port du service. |
| 17 | La référence qualité affichée ≠ celle appliquée | `GET /api/clustering/quality` publie `silhouette: 0,5183` (valeur brute en base) alors que le garde-fou la **plafonne à l'ancre 0,4256** au moment de la comparaison (`quality.py:168`). Le garde-fou est correct ; c'est l'affichage qui trompe l'exploitant. |
| 18 | Incohérence de casse entre MS1 et MS5 | MS5 accepte `sens=matin` ; MS1 exige `"MATIN"` (`Cannot deserialize … not one of [SOIR, MATIN]`). Deux services, deux conventions, sur le même concept métier. |
| 19 | `/actuator/gateway/routes` renvoie **404** | Pourtant listé dans `management.endpoints.web.exposure.include`. Aucun moyen d'inspecter les routes de la passerelle en fonctionnement. |
| 20 | 10 267 notifications, **100 % en ECHEC**, 0 envoyée | `GET /api/notifications/stats` : `{"echecs":10267,"envoyes":0,"alertesAdmin":19,"total":10267}`. État documenté (piège n° 23) : aucun appareil réel n'est enregistré. Le canal est câblé et correct, jamais exercé pour de vrai. |

---

## 4. Ce qui est confirmé — les correctifs tiennent

Sept correctifs documentés dans `CLAUDE.md` ont été **rejoués contre la stack vivante** et
tiennent tous.

| Piège | Correctif | Preuve mesurée ce jour |
|---|---|---|
| **n° 14** | MS5 `continue_straight=false` | Convergence `distance_m` ↔ longueur réelle de la géométrie : **0,05 % · 0,03 % · 0,02 %** sur les groupes 1, 2 et 3 |
| **n° 19** | `choisir_k` robuste + hystérésis | **0/301 élèves changent de bus** au recalcul appliqué (contre 12–13 % avant) |
| **n° 21a** | Le masque ne s'écrit jamais | Masque `••••••1234` renvoyé au serveur → valeur d'origine **intacte** |
| **n° 21b** | `.env` = amorçage, MS13 = surcharge | 3 secrets **vides** côté MS13, MS9 reste `configured: true` |
| **n° 21c** | `models-check` normalisé | **Verdict OK** : les 3 modèles de la cascade (`gpt-oss-120b`, `gpt-oss-20b`, `gemini-flash-latest`) sont réellement servis |
| **n° 23** | Verrou d'entrée de zone | Bus **garé** à l'école, 30 pings avec bruit GPS → **26 notifications pour 27 parents** (≈ 1 par parent). Avant correctif : 810 |
| **n° 24** | Jeton FCM idempotent | Même jeton enregistré 3 fois → **200, 200, 200** (HTTP 500 avant correctif) |

**Autres vérifications réussies :**

- **MS13 propagation à chaud : 2,30 s**, sans redémarrage (`ms11.seuil_vitesse_kmh`
  90 → 85, lu dans `GET /api/analytique/live`), puis restauration.
- **MS13 atomicité** : un lot contenant une valeur hors bornes → **HTTP 400 et aucune
  écriture** ; `POST /reset` restaure le défaut du catalogue.
- **Limiteur de la passerelle conforme** : 40 connexions parallèles → **36 × 429**
  (seaux 20/40 + 5/10 empilés). ⚠️ En **séquentiel**, rien ne se déclenche — un test
  séquentiel serait faussement rassurant.
- **Routage MS13 étanche** : `GET :8080/api/parametres/internal` → **404**, `:8092` → 200.
- **RBAC serveur solide** : **30 combinaisons rôle × route interdite** testées,
  **28 correctes** (les 2 écarts sont les 401 de MS7, défaut n° 8) — dont `/llm/chat`
  refusé à l'ADMIN, `/planification/tournee` refusé au PARENT, `/messages/diffusion`
  refusé à l'ADMIN, MS9 `/admin/query` refusé au PARENT. Et **15 accès légitimes en
  lecture** vérifiés pour les 3 rôles, tous à 200.
  ⚠️ Détail de méthode : en Spring, `@Valid` s'exécute **avant** `@PreAuthorize`. Un corps
  vide renvoie 400 et le contrôle de rôle n'est jamais atteint — le test ne prouverait
  rien. Les corps envoyés sont donc valides.
- **MS11 conforme aux métriques gelées** : `iforest_curated`, PR-AUC 0,9127, précision
  0,70, rappel 0,875.
- **web-admin : 27 routes rendues, 0 erreur console, 0 requête réseau en échec**, dans un
  Chrome réel, après une connexion réelle par le formulaire, pour les 3 rôles.
- **Chaîne d'incident complète** : MS10 → RabbitMQ → MS4 produit `INCIDENT_SIGNALE` et
  `INCIDENT_RESOLU`.
- **Trajet non idempotent confirmé** : second démarrage → `400 « Un trajet est déjà en
  cours »`, exactement le cas que la file hors ligne de `chauffeur-mobile` réconcilie.
- **Route figée exposée** : `GET /api/trajets/bus/{id}/route` → 338 points + totaux
  (9 410 m / 18,43 min) ⇒ surveillance de déviation MS11 armée.

---

## 5. Zones non couvertes — à énoncer en soutenance

- **Aucun test sur `ms3-localisation`, `ms13-parametres`, `ms-common`** — GPS/WebSocket,
  configuration centrale et JWT partagé, soit trois briques critiques. Et cinq autres
  modules ont leurs tests désactivés (défaut n° 6).
- **`web-admin` n'a toujours aucun test dans son dépôt.** Le balayage
  `scripts/recette/balayage_front.mjs` livré ici le remplace pour le rendu et le RBAC, mais
  ne teste aucune logique métier (formulaires, calculs, états).
- **Aucune intégration continue** (ni `.github/workflows`, ni `.gitlab-ci.yml`) : rien ne
  rejoue ces suites automatiquement. C'est la cause première des défauts n° 2 et n° 6.
- **Jamais vérifié sur téléphone physique** : émission GPS réelle, tenue du service de
  premier plan écran verrouillé, *Doze* constructeur, batterie, notifications poussées.
- **Aucune cible iOS.**
- **Le canal push n'a jamais délivré un seul message réel** (défaut n° 20).
- **MS9 : évaluation LLM limitée au smoke live** — le golden set complet à 4 modèles du
  23/08 n'a pas été rejoué (choix assumé : quota API). `models-check` confirme en revanche
  que la cascade configurée est bien servie aujourd'hui.
- **Les apps Flutter n'ont pas été balayées dans le navigateur** : leurs 131 tests
  (93 + 38) passent, mais le rendu web sur `:5174` / `:5175` n'a pas été exercé dans cette
  campagne.

---

## 6. Rejouer cette recette

```bash
# tout ce qui ne demande pas la stack (suites unitaires, analyse, build)
scripts\recette\tout.cmd offline

# tout ce qui interroge la stack vivante (elle doit être démarrée)
scripts\recette\tout.cmd live

# ou pièce par pièce
python scripts/recette/contrats.py          # phase 2 — contrats & RBAC
scripts\recette\newman.cmd                  # phase 3 — collection Postman
set PYTHONIOENCODING=utf-8 && python e2e_integration_test.py   # phase 4
python scripts/recette/temps_reel.py        # phase 5 — chaîne temps réel
python scripts/recette/config_et_push.py    # phase 7 — MS13 & MS4
node scripts/recette/balayage_front.mjs     # phase 8 — 27 routes dans Chrome
```

Résultats bruts et captures d'écran : `scripts/recette/resultats/`
(`contrats.json`, `newman.json`, `temps_reel.json`, `config_et_push.json`,
`balayage_front.json`, `deviation_couverture.json`, `captures/*.png`).

**Prérequis** : `docker-compose up -d`, `docker start osrm_meknes`, `start-all-ms.bat`,
`bun run dev` dans `frontend/web-admin`, et l'environnement conda `nlp` pour Python.
La phase 8 exige `puppeteer-core` (installé dans `frontend/web-admin`) et Chrome.

---

> 📄 **Suite de ce document : [`PLAN_CORRECTIONS.md`](PLAN_CORRECTIONS.md)** — le planning de
> correction en 7 lots. Une revue de code menée après cette recette, ciblée sur les
> **interactions entre acteurs**, a révélé **13 défauts de portée supplémentaires** que les
> tests ci-dessus ne couvraient pas : le registre consolidé y compte **33 défauts**, pas 20.

## 7. Ordre de traitement suggéré

| Priorité | Défauts | Effort estimé |
|---|---|---|
| **Avant toute démonstration publique** | n° 1 (escalade ADMIN), n° 2 (301 élèves ouverts) | quelques lignes chacun |
| **Avant la soutenance** | n° 10 (k=9 vs k=7 — décider et documenter), n° 12 (G1 non déterministe), n° 13 et 14 (les scripts doivent démarrer chez le lecteur) | faible |
| **À documenter comme dette assumée** | n° 3, 4, 5, 7, 9, 11, 20 | — |
| **Cosmétique** | n° 15 à 19 | faible |

Les défauts n° 1 et n° 2 sont les seuls dont la présence, une fois connue, ne peut pas se
défendre en soutenance : ils sont chacun corrigeables en quelques lignes, et un jury qui
les découvre lui-même posera la question autrement.
