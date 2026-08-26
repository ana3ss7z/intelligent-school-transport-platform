# Plan de correction — vers une application défendable

**Établi le 26 août 2026**, à partir de deux sources : la [recette de bout en
bout](RECETTE_FINALE.md) (20 défauts mesurés contre la stack vivante) et une **revue de code
ciblée sur les interactions entre acteurs**, menée ensuite, qui en a révélé **13 de plus**.
Total : **33 défauts**.

---

## 1. Réponse honnête : non, tous les scénarios n'ont pas été testés

La recette a couvert **exhaustivement la surface de contrat** — 45 combinaisons rôle × route,
27 routes front × 3 rôles, les 7 correctifs documentés. Elle a couvert **partiellement les
pipelines** — GPS→ETA→notification, présence, anomalies, incident, configuration à chaud.

Elle n'a **pas** couvert la matrice **acteur → acteur**. Or c'est précisément là que se logent
les défauts restants : une route peut être correctement ouverte au bon *rôle* et laisser
malgré tout un acteur agir sur les données d'un autre acteur du **même** rôle.

| Couche | Question posée | Testée ? |
|---|---|---|
| Authentification | Le jeton est-il valide ? | ✅ oui |
| Autorisation (RBAC) | Ce **rôle** a-t-il le droit d'appeler cette route ? | ✅ oui, 45 combinaisons |
| **Portée (propriété)** | Ce **compte précis** a-t-il le droit d'agir sur **cet objet précis** ? | ❌ **presque pas** |

Trois des 20 défauts de la recette relevaient de la portée. La revue de code en a trouvé
**13 autres**, tous du même moule. C'est un **angle mort systématique**, pas une série
d'oublis isolés.

### Ce qui reste non exercé, au-delà de la portée

- **Messagerie complète** : chauffeur → admin, admin → chauffeur, badges lu/non-lu des deux
  côtés, diffusion chauffeur → parents du bus.
- **Assistant MS9** : le smoke live (6 questions fr/ar/darija, injection, hors-portée,
  écriture) était prévu — **il n'a pas été joué**. Seul `models-check` a été vérifié.
- **NL2SQL admin** : aucune requête réellement exécutée.
- **Isolation entre familles** : un parent voit-il uniquement ses notifications, ses messages,
  ses enfants ?
- **Les deux applications Flutter** : 131 tests passent, mais aucun écran n'a été exercé dans
  un navigateur contre le backend réel.
- **WebSocket GPS** : jamais testé, alors qu'il alimente les trois frontends.

---

## 2. Registre consolidé des 33 défauts

### 🔴 Bloquants — exploitables sans compte (2)

| # | Défaut | Site |
|---|---|---|
| B1 | `POST /api/auth/register` accepte `role` → jeton ADMIN pour un inconnu | `AuthController.java:58` |
| B2 | `GET /api/eleves` `permitAll` → 301 élèves + domiciles GPS sans jeton | `ms2 SecurityConfig.java:54` |

### 🟠 Portée / IDOR — un compte agit sur les données d'un autre (15)

Trois trouvés par la recette (P1–P3), **douze par la revue de code** (P4–P15).

| # | Endpoint | Qui peut en abuser | Site |
|---|---|---|---|
| P1 | `GET /api/eleves/parent/{parentId}` | tout rôle authentifié, n'importe quel parent | `EleveController.java:55` |
| P2 | `GET /api/gps/eleve/{id}/historique` | tout PARENT, n'importe quel élève | `GpsController.java:90` |
| P3 | `/carte` (front) sans garde de rôle | PARENT et CHAUFFEUR voient toute la flotte | `App.tsx:63` |
| P4 | **`PATCH /api/eleves/{id}/presence`** | **tout CHAUFFEUR, n'importe quel élève** → notification poussée au parent d'autrui | `EleveController.java:124` |
| P5 | `POST /api/incidents` (`busId` dans le corps) | tout CHAUFFEUR, n'importe quel bus → alerte les parents de ce bus | `IncidentController.java:31` |
| P6 | `GET /api/incidents/bus/{busId}` | tout PARENT, n'importe quel bus | `IncidentController.java:66` |
| P7 | **`GET /api/trajets/bus/{busId}/route`** | **tout PARENT** → polyligne complète de la tournée, donc **la rue de chaque famille** | `TrajetController.java:76` |
| P8 | `GET /api/trajets/bus/{busId}/actif` | tout PARENT, n'importe quel bus | `TrajetController.java:63` |
| P9 | `POST /api/trajets/demarrer` (`busId` du corps non validé) | un CHAUFFEUR démarre un trajet sur le bus d'un collègue | `TrajetService.java:37` |
| P10 | `GET /api/eleves/bus/{busId}` | tout CHAUFFEUR, n'importe quel bus | `EleveController.java:62` |
| P11 | `POST /api/planification/tournee?groupeId=` | tout CHAUFFEUR, n'importe quel groupe → domiciles de toutes les familles | `ms5 main.py:75` |
| P12 | `GET /api/gps/bus/tous` et `/bus/{id}/derniere` | tout rôle authentifié, aucune annotation | `GpsController.java:46,69` |
| P13 | `DELETE /api/notifications/device-token/{token}` | tout PARENT/CHAUFFEUR peut désactiver le jeton d'autrui | `NotificationController.java:47` |
| P14 | **`ws://:8083/ws/gps`** | **personne n'a besoin de jeton** ; filtre `ALL` par défaut, origine `*` → tout le trafic GPS bus **et élèves** | `WebSocketConfig.java:33` |
| P15 | `POST /api/messages {destinataireId: <parentId>}` | un ADMIN dépose un message direct dans la boîte d'un parent, hors de tout fil | `MessageService.java:46` |

> P7 et P14 sont les plus lourds en confidentialité : la polyligne d'une tournée trace la rue
> de chaque famille — c'est exactement ce que MS5 refuse délibérément de livrer au parent
> (`/mes-enfants` ne renvoie ni coordonnées ni nom d'autrui). MS1 le donne gratuitement.

### 🟡 RBAC creux et cohérence (4)

| # | Défaut | Site |
|---|---|---|
| C1 | ADMIN autorisé à `terminer` un trajet mais refusé par le contrôle de propriété → **bus bloqué sans recours** | `TrajetService.java:69` |
| C2 | MS7 renvoie 401 au lieu de 403 (pas d'`accessDeniedHandler`) → le front **déconnecte** | `ms7 SecurityConfig.java:44` |
| C3 | `POST /api/messages` admin : `destinataireId` non validé comme chauffeur existant → fils fantômes | `MessageService.java:46` |
| C4 | `sens` : MS5 accepte `matin`, MS1 exige `MATIN` | `TrajetRequest` / `ms5 main.py` |

### 🟡 Dette technique visible (5)

| # | Défaut | Site |
|---|---|---|
| D1 | 5 modules à `<skipTests>true</skipTests>` → `mvn test` vert en n'exécutant rien | 5 × `pom.xml` |
| D2 | 7 files RabbitMQ déclarées sans consommateur, **28 944 messages** | 3 × `RabbitMQConfig.java` |
| D3 | `flutter analyze` chauffeur : 5 erreurs (fichier Firebase orphelin) | `chauffeur-mobile/lib/firebase_options.dart` |
| D4 | `e2e_integration_test.py` ne démarre pas sur console Windows (cp1252) | racine |
| D5 | `pytest ms6-clustering/tests` échoue depuis la racine (`.env` racine absorbé) | `ms6-clustering/config.py` |

### 🔵 Cohérence documentaire et ML (5)

| # | Défaut | Décision attendue |
|---|---|---|
| M1 | Production à **k=9 bus**, documentation à **k=7** | trancher : réinitialiser l'état ou publier k=9 |
| M2 | `domaine_entrainement: null` → la garde MS12 ne tient qu'au CSV | écrire les bornes dans l'artefact |
| M3 | Référence qualité **affichée** 0,5183 ≠ **appliquée** 0,4256 | publier la valeur plafonnée |
| M4 | Endpoints « Public » fermés par la passerelle (401) | corriger les tableaux du `CLAUDE.md` |
| M5 | `/actuator/gateway/routes` → 404 | activer ou retirer de la configuration |

### 🔵 Constats sans correction (3)

`incident.signale` ne notifie **que les parents** (ni admin ni chauffeur), contrairement à ce
qu'annonce le commentaire du code · le verrou d'arrivée MS4 est **en mémoire**, perdu au
redémarrage · 10 267 notifications à 100 % en `ECHEC`, aucun appareil réel enregistré.

---

## 3. Le planning — 7 lots, environ 4,5 jours

**Le principe d'ordonnancement compte autant que le contenu :** le lot 1 écrit les tests de
scénarios **avant** de corriger quoi que ce soit. Ils partiront **rouges** sur les 15 défauts
de portée — c'est le but. On ne corrige ensuite que ce qui fait passer un test au vert, et la
non-régression est acquise par construction.

```
J1 ─ Lot 0 bloquants ──► Lot 1 harnais de scénarios (rouge)
J2 ─ Lot 2 portée / IDOR ─────────────────────────► (vert)
J3 ─ Lot 3 RBAC creux ──► Lot 4 WebSocket authentifié
J4 ─ Lot 5 dette ───────► Lot 6 cohérence doc & ML
J5 ─ Lot 7 non-régression complète + mise à jour des documents
```

---

### Lot 0 — Bloquants · une demi-journée · à faire en premier, quoi qu'il arrive

**B1 — auto-promotion ADMIN.** Une ligne.
`AuthController.java:58` : `.role(req.getRole())` devient `.role(Role.PARENT)`.
Laisser le champ dans le DTO (les scripts existants l'envoient) mais l'ignorer côté serveur.
`POST /api/auth/users`, déjà `hasRole('ADMIN')`, reste la seule voie pour créer un CHAUFFEUR
ou un ADMIN.

**B2 — `GET /api/eleves` ouvert.** Ce n'est *pas* une ligne : trois services Python en
dépendent sans jeton (`ms5/ms2_client.py`, `ms6/ms2_client.py`,
`ms12/context/roster_ms2.py`), tous en appel **direct** à `:8082`.

> ⚠️ Le motif MS13 (`/internal` non routée par la passerelle) **ne s'applique pas tel quel** :
> le prédicat de la passerelle est `Path=/api/eleves/**`, qui avale tout chemin sous
> `/api/eleves`. Une route `/api/eleves/internal` resterait joignable depuis le web.

Solution : créer **`GET /internal/eleves`** dans MS2 — préfixe **hors** `/api/eleves/**`, donc
non routé par la passerelle, `permitAll` dans `SecurityConfig`. Basculer les trois clients
Python dessus, puis **supprimer la ligne 54**.

**Vérification** : `scripts\recette\newman.cmd` doit passer à **88/88** (c'est l'assertion 13
qui remonte), `curl :8080/internal/eleves` → **404**, `curl :8082/api/eleves` → **401**, et
MS5 `/tournee` doit continuer de répondre.

---

### Lot 1 — Harnais de scénarios acteur ↔ acteur · une demi-journée · avant toute correction

Nouveau script `scripts/recette/scenarios.py`, sur le modèle de `contrats.py`. Il instancie
**six comptes réels** — 1 admin, 2 chauffeurs de bus différents, 3 parents de bus différents —
et vérifie systématiquement les deux faces de chaque interaction : *l'acteur légitime peut*,
*l'acteur voisin ne peut pas*.

| Famille | Scénarios |
|---|---|
| **Messagerie** | chauffeur A écrit → l'admin le voit dans `conversations` · l'admin répond → A le voit, **B ne le voit pas** · badges non-lus des deux côtés · diffusion de A → **exactement** les parents du bus de A, aucun autre · les diffusions n'apparaissent pas dans le fil admin↔chauffeur |
| **Présence** | chauffeur A pointe un élève de A → notification au **bon** parent · A pointe un élève de **B** → doit être refusé (P4) |
| **Trajets** | A démarre sur son bus → OK · A démarre sur le bus de B → doit être refusé (P9) · parent 1 lit la route du bus de son enfant → OK · du bus d'un autre → refusé (P7/P8) |
| **Incidents** | A signale sur son bus → OK · sur le bus de B → refusé (P5) · parent 1 lit les incidents de son bus → OK · d'un autre bus → refusé (P6) |
| **Élèves & GPS** | parent 1 lit ses enfants → OK · les enfants de parent 2 → refusé (P1) · historique GPS d'un élève tiers → refusé (P2) · `bus/tous` par un parent → refusé (P12) |
| **Assistant MS9** | 6 questions : opérationnelle FR · darija · injection de prompt · enfant d'un autre parent · demande d'écriture · NL2SQL admin. Attendu : utile sur 2, refus sur 3, SQL + tableau sur la dernière |
| **Planification** | chauffeur A demande la tournée du groupe de B → refusé (P11) · parent → `/mes-enfants` ne renvoie que ses enfants, sans coordonnées d'autrui |
| **Notifications** | parent 1 ne voit que ses notifications · désactiver le jeton d'autrui → refusé (P13) |
| **WebSocket** | connexion sans jeton → doit être refusée (P14) |

**À l'issue du lot 1, le script est rouge sur 15 assertions.** C'est le contrat du lot 2.

---

### Lot 2 — Contrôle de propriété · une journée · le cœur du chantier

Un motif unique, appliqué partout. Java l'a déjà : `@AuthenticationPrincipal UserPrincipal`
est installé par le `JwtAuthFilter` de MS1, MS2, MS3 et MS4 — **aucune plomberie à ajouter**.
Le modèle correct existe déjà dans le projet : `ms5-planification/main.py:42` (`verify_parent`)
et `ms9-llm/tools.py:123` (`_check_scope` sur `allowed_bus_ids`).

| Cible | Correction |
|---|---|
| P1 `eleves/parent/{id}` | `@PreAuthorize("hasRole('ADMIN') or #parentId == principal.userId")` |
| P4 présence | injecter le principal, vérifier que `eleve.busId` est le bus du chauffeur |
| P10 `eleves/bus/{id}` | idem |
| P5 `POST /incidents` | vérifier `req.busId` = bus du chauffeur (MS1 `/api/bus/{id}/chauffeur`, déjà `permitAll` interne) |
| P6 `incidents/bus/{id}` | PARENT : le bus doit être celui d'un de ses enfants |
| P7 P8 `trajets/bus/{id}/*` | même contrôle côté MS1 |
| P9 `trajets/demarrer` | vérifier que `busId` appartient au chauffeur |
| P11 MS5 `/tournee` | CHAUFFEUR : le groupe doit être celui de son bus |
| P2 P12 MS3 | **`/api/gps/eleve/*` n'est appelé par aucun client** — vérifié. Les restreindre à ADMIN, ou les supprimer. `bus/tous` et `bus/{id}/derniere` : annoter, et scoper le parent à ses bus |
| P13 device-token | vérifier que le jeton appartient au demandeur |
| P15 messages | refuser un `destinataireId` dont le rôle n'est pas CHAUFFEUR |
| P3 `/carte` | ajouter `roles={["ADMIN"]}` dans `App.tsx:63` |

⚠️ **MS2 et MS3 n'ont pas de client MS1/MS2.** Pour P5, P6, P7 et P8 il faut un petit client
HTTP interne — le motif existe déjà dans MS4 (`BusLookupService`, `ParentLookupService`), à
copier tel quel plutôt qu'à réinventer.

**Vérification** : `scenarios.py` passe au vert, `contrats.py` monte de 60/66 à 66/66.

---

### Lot 3 — RBAC creux et cohérence · une demi-journée

- **C1** : `terminer(id, userId, role)` — sauter le contrôle de propriété si `role == ADMIN`.
  Copier le même motif dans `demarrer` n'est **pas** souhaitable : un admin qui démarre se
  verrait estampillé `chauffeurId`. Ne toucher que `terminer`.
- **C2** : ajouter l'`accessDeniedHandler` de `ms1-bus/SecurityConfig.java:37-41` dans MS7
  (et dans MS2, qui n'en a pas non plus). Copier-coller, l'import existe déjà.
- **C3** : valider `destinataireId` contre `GET /api/auth/users?role=CHAUFFEUR`.
- **C4** : accepter les deux casses côté MS1 (désérialisation d'enum insensible à la casse).

---

### Lot 4 — WebSocket GPS authentifié · une demi-journée · chantier transverse

Aujourd'hui : aucun jeton, origine `*`, filtre `ALL` par défaut — **toutes les positions de
tous les bus et de tous les élèves**, pour qui ouvre la socket.

Correction : un `HandshakeInterceptor` qui lit le jeton en paramètre de requête
(`?token=…` — les navigateurs n'autorisent pas d'en-tête sur un WebSocket), le valide avec le
même `JwtUtils`, et stocke rôle et `userId` dans les attributs de session. Puis, dans
`GpsWebSocketHandler`, filtrer la diffusion selon le rôle : ADMIN voit tout, CHAUFFEUR son
bus, PARENT les bus de ses enfants.

⚠️ **Trois clients à mettre à jour ensemble** : `web-admin/src/hooks/useGpsSocket.ts:4`,
`parent-mobile/lib/services/gps_socket.dart`, `chauffeur-mobile/lib/services/gps_socket.dart`.
Les deux applications Flutter ont un `gps_socket.dart` jumeau — ne pas en corriger un seul.

Restreindre aussi `setAllowedOrigins("*")` aux origines réelles (5173 / 5174 / 5175).

---

### Lot 5 — Dette technique · une demi-journée

- **D1** : supprimer `<skipTests>true</skipTests>` dans les 5 `pom.xml` (une ligne chacun,
  dans `<properties>`, pas dans un plugin). ⚠️ Les 5 tests réactivés sont des
  `@SpringBootTest` **qui vont peut-être échouer** — c'est le but ; les faire passer fait
  partie du lot.
- **D2** : supprimer les déclarations de files sans consommateur dans les `RabbitMQConfig` de
  MS2, MS3 et MS10 — **garder les beans `transportExchange()`**, les publieurs en dépendent.
  Purger les 28 944 messages résiduels depuis la console RabbitMQ.
- **D3** : supprimer `chauffeur-mobile/lib/firebase_options.dart` et `firebase.json`
  (orphelins : Firebase n'est pas une dépendance de cette application).
- **D4** : ajouter la reconfiguration de sortie en UTF-8 en tête de
  `e2e_integration_test.py` — le motif est déjà dans `scripts/recette/contrats.py:27`.
- **D5** : `extra="ignore"` dans les `Settings` de MS6, ou `env_file` en chemin absolu.

---

### Lot 6 — Cohérence documentaire et ML · une demi-journée

- **M1** — la décision à trancher : effacer `ms6-clustering/data/last_selection.json` fait
  repasser à k=7, conforme au mémoire, **au prix d'un churn** (des enfants changent de bus) ;
  le garder impose de publier k=9 et d'expliquer l'hystérésis. Les deux se défendent —
  **le churn mesuré à 0 % est un argument fort pour ne rien toucher et documenter k=9**.
- **M2** : faire écrire `domaine_entrainement` par `train.py` dans `eta_config.json`, ou au
  minimum journaliser un avertissement quand le repli sur le CSV est utilisé.
- **M3** : exposer la référence **plafonnée** dans `GET /api/clustering/quality`.
- **M4** : corriger la colonne « Public » des tableaux du `CLAUDE.md` — vrai en direct, faux
  via la passerelle.
- **M5** : activer l'endpoint actuator de la passerelle, ou le retirer de la configuration.

---

### Lot 7 — Non-régression · une demi-journée

```
scripts\recette\tout.cmd offline         # attendu : mvn test > 18, flutter analyze 0
scripts\recette\tout.cmd live            # attendu : contrats 66/66, Newman 88/88
python scripts/recette/scenarios.py      # attendu : 100 % vert
node scripts/recette/balayage_front.mjs  # attendu : 42/42
```

Puis : rejouer le balayage front, exercer les **deux applications Flutter dans le navigateur**
contre le backend corrigé (jamais fait), et mettre à jour `RECETTE_FINALE.md`, `CLAUDE.md` et
`README.md` avec les chiffres d'après correction.

---

## 4. Ce que « parfaite » ne pourra pas signifier

À énoncer soi-même en soutenance plutôt que de le laisser découvrir :

- **Aucune intégration continue.** C'est la cause première de B2 et de D1 : un test qui existe
  mais que personne ne rejoue finit par documenter une faille. Y remédier dépasse ce plan.
- **Aucun téléphone physique** n'a jamais été testé : émission GPS réelle, service de premier
  plan écran verrouillé, veille constructeur, notifications poussées.
- **Aucune cible iOS.**
- **Le canal push n'a jamais délivré un message réel** — câblé, corrigé, testé unitairement.
- **Les ports de service ne sont pas isolés.** Le projet les traite comme privés, mais rien ne
  les protège : tous écoutent sur la même machine. Un réseau Docker applicatif serait la vraie
  réponse à toute la famille B2.
- **La règle de déviation reste structurellement faible** (16 à 29 % de couverture à 300 m).
  Elle se corrige en mesurant la distance **le long** de la polyligne plutôt qu'au point le
  plus proche — c'est le correctif `depuisAlongM` déjà appliqué à l'ETA (piège n° 13), jamais
  transposé ici. Chantier à part entière, hors de ce plan.

---

## 5. Si le temps manque

L'ordre de valeur décroissante, pour un arbitrage sous contrainte :

1. **Lot 0** — non négociable, deux failles exploitables sans compte.
2. **Lot 2 restreint à P4, P7 et P14** — les trois qui exposent des données de familles tierces.
3. **Lot 5 D1 + D4 + D5** — sans quoi les chiffres du mémoire ne sont pas reproductibles par un
   lecteur.
4. **Lot 6 M1** — une décision à prendre, pas du code : k=7 ou k=9 dans le mémoire.

Le reste peut être présenté comme **dette connue, chiffrée et hiérarchisée** — ce qui, en
soutenance, vaut mieux qu'un correctif improvisé la veille.
