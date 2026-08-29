# CLAUDE.md — Transport Scolaire Intelligent
## État au 20 août 2026 — briques IA (MS6/MS12/MS5/MS11) + temps réel (e2e) + **3 espaces web (admin · chauffeur · parent)** + **messagerie** + **déviation d'itinéraire** + **MS9 assistant LLM parent (Phase A)** + **apps mobiles PARENT & CHAUFFEUR Flutter** + **ETA le long de la tournée** livrés

---

## 🎯 Résumé du projet

Système de transport scolaire intelligent basé sur une architecture **microservices Spring Boot + Python FastAPI**, développé dans le cadre d'un **PFE Master SDIA (M2)**. Le projet digitalise et optimise le transport des élèves à **Meknès, Maroc** (300 élèves seedés avec coordonnées GPS réelles).

> **Données en base = v2** (`seed_eleves_meknes_v2.sql`, chargé via TRUNCATE RESTART IDENTITY → ids 1..300) :
> 6 zones / ~20 secteurs, **destination école** (Al Massira, 33.893/-5.5455), **oued** séparateur, **5 % dispersés**.
> Cohérent avec les notebooks MS6, le CSV `ms6-clustering/data/eleves_meknes.csv` et la matrice OSRM cachée.
> *(v1 `seed_eleves_meknes.sql` = ancien jeu, remplacé.)*

**Étudiant :** Anass  
**Encadrant :** Pr. Ali Bekri  
**Faculté :** Faculté des Sciences Moulay Ismail, Meknès  
**Planning :** S1 à S15 (mai → août 2026)  
**État actuel :** Les 4 briques IA sont livrées — **MS6** clustering capacitaire routier, **MS12** prédiction ETA,
**MS5** VRP (tournées), **MS11** détection d'anomalies. La **couche d'intégration temps réel** est câblée et
**validée e2e (8/8)** : **G1** pipeline ETA→notif parents, **G3** monitor anomalies GPS live, **G5** présence
« enfant à bord », **B1** liaison groupe↔bus (busId propagé), **garde-fou qualité** clustering, déclencheur
« nouveau bus » MS1→MS6. **Données réalistes générées** (216 parents/fratries, 10 chauffeurs, flotte de bus ;
`generer_comptes.py` idempotent).

**NOUVEAU — Console d'administration web (`frontend/web-admin/`, React 18 + Vite + TS + Bun + Tailwind v4)** :
dashboard (KPIs + graphiques Recharts + auto-refresh), carte live (bus interpolés, traînées, flèches, arrêts
numérotés, pulse anomalie, ETA live→école, tournées OSRM), clustering (Pareto, diagnostics, verdict qualité,
**carte des clusters** enveloppes+filtres = dernier résultat DB **+ carte de prévisualisation** d'une simulation),
prévisions ETA par arrêt, incidents (MS10), analytique anomalies (MS11 scan), notifications, **CRUD élèves/bus/
utilisateurs** + **liaisons parent↔enfant & chauffeur↔bus**, présence, pagination/tri, export CSV, paramètres.
Infra pro : toasts, ErrorBoundary, skeletons, dialogues de confirmation, command palette ⌘K, nav mobile, code-splitting, RBAC.

**Deltas backend liés à l'UI** : MS7 `GET/POST/PUT/DELETE /api/auth/users` (ADMIN, mot de passe jamais exposé,
anti-auto-suppression) ; MS3 fix WebSocket (`ConcurrentWebSocketSessionDecorator` — écritures concurrentes) ;
MS5 `/tournees` parallélisé (`asyncio.gather` + OR-Tools en thread, ~43 s→9 s) ; MS6 `/production` renvoie
`assignments` (affectation par élève, pour prévisualisation carte même non appliquée) ; `bus_simulator.py` v2 data-driven.

**NOUVEAU (21/07) — Espace CHAUFFEUR + espace PARENT + messagerie + déviation (web-admin RBAC, 3 rôles) :**
- **Espace chauffeur** (`ChauffeurHome` + pages) : cycle de vie **Trajet** (entité MS1 `trajets`, démarrer/terminer),
  **pointage** montée/dépose (→ notif parent), **arrêt courant** surligné + distance, carte/ETA de son bus,
  incidents, **historique** (`GET /api/trajets/mes-trajets`), notifs entrantes (incident résolu de son bus + messages).
  Tableau admin **« Trajets en cours »** (`GET /api/trajets/actifs`).
- **Déviation d'itinéraire (UC-8 3/3)** : au démarrage, le front envoie `groupeId` + `geometrie` (tournée MS5) ;
  MS1 les persiste sur le `Trajet` et les diffuse (`trajet.demarre`) ; **MS11** (queue `ms11.trajet.queue`) fige la
  route et détecte `DEVIATION_ITINERAIRE` (distance point→polyligne > seuil) → `anomalie.detectee` + `/live`.
  Purge à `trajet.termine`. Seuils `.env` MS11 : `SEUIL_DEVIATION_M`, `DEVIATION_PINGS_CONSECUTIFS`.
- **Messagerie (MS4, entité `Message` dédiée)** : **chauffeur ↔ administration** en conversation/chat avec
  historique + lu/non-lu + badge (`/api/messages` : envoyer, ma-conversation, conversations, conversation/{id},
  non-lus). Route gateway `ms4-messages` (`/api/messages/**`). *(Remplace l'ancien POST /notifications/message.)*
- **Espace PARENT** : **Mon espace** (enfants + bus + présence + **compte à rebours** « bus arrive dans ~N min »
  vers école (matin) ou domicile (soir), **seulement si trajet démarré** via `GET /api/trajets/bus/{id}/actif`),
  **Carte de mon enfant** (bus filtré + ETA), **Messagerie réception seule** (`GET /api/messages/parent`),
  **Notifications**. **Diffusion chauffeur → tous les parents du groupe** (`POST /api/messages/diffusion?busId=`,
  flag `Message.diffusion`, isolée des fils). MS12 `/api/eta/predict` ouvert au rôle **PARENT**.
- **Deltas back** : MS1 `Trajet` (+`groupeId`,`geometrie`) + `/api/trajets/{mon-actif,mes-trajets,bus/{id}/actif,demarrer,{id}/terminer}` + route interne `/api/bus/{id}/chauffeur` (permitAll) ; MS2 présence publiée aussi sur `false` (dépose soir) ; MS4 `BusLookupService`, listener incident→chauffeur, enum `ENFANT_DEPOSE/TRAJET_*/MESSAGE_ADMIN`.
- **Panneau de simulation** `html_tests/simulation-control.html` : pilote **tous les scénarios** ciblés sur un
  chauffeur/bus (trajet, mouvement GPS, présence, anomalies, déviation, incident, diffusion, message) en HTTP via la
  Gateway, connecté comme admin+chauffeur+parent, avec journal live + liens vers les pages React à observer.
- **Fix** : `usePolling` n'utilise plus `useTransition` (rendu concurrent) → un simple booléen `refreshing` (élimine
  l'erreur récupérable React #520 sur dashboard/incidents/notifications, même UX).
- **Migration DB** (base existante) : `ALTER TABLE messages ADD COLUMN IF NOT EXISTS diffusion boolean NOT NULL
  DEFAULT false;` et `ALTER TABLE notifications` CHECK complété (`ENFANT_DEPOSE, TRAJET_DEMARRE, TRAJET_TERMINE,
  MESSAGE_ADMIN`) — Hibernate `ddl-auto=update` n'ajoute pas une colonne NOT NULL sur table peuplée ni ne met à jour un CHECK.
- **Validation navigateur (Chrome réel, puppeteer)** : admin (13 pages), chauffeur (7), parent (4) — rendus OK,
  0 erreur bloquante. Briques IA re-vérifiées UP + résultats conformes (MS6 k=6/silhouette 0.52, MS12 elasticnet +52.7 %, MS11 iforest_curated PR-AUC 0.91, MS5 TSP OSRM).

**NOUVEAU — MS9 Assistant LLM (chatbot parent, Phase A) :** microservice `ms9-llm/` (FastAPI :8089, env `nlp`,
route gateway `ms9-llm → /api/llm/**` déjà présente). **Agent tool-calling « maison »** (sans LangChain) **agnostique**
(client OpenAI-compatible interchangeable). Le parent pose des questions opérationnelles (« où est le bus ? »,
« dans combien de temps ? », « est-il monté ? ») ; le LLM appelle des **outils Python** qui interrogent les MS
**avec le JWT du parent**, strictement **limité à ses enfants** (garde de portée : `parentId` du JWT, `busId ∈ enfants` ;
jamais confiance aux ids du modèle). Outils : `get_mes_enfants` (MS2), `get_position_bus` (MS3, + **reverse geocoding
Nominatim/OSM** → rue/quartier), `get_eta_ecole` (MS12), `get_trajet_actif` (MS1), `get_incidents_bus` (MS10).
Robustesse : **pré-fetch enfants (1×)** + injection contexte au prompt, **tool calls en parallèle** (`asyncio.gather`),
**historique propre** (user/assistant seulement → évite le 400 OpenAI), **cascade providers 70b → 8b → Gemini**
(`openai/gpt-oss-120b` qualité → `openai/gpt-oss-20b` repli budget séparé → Gemini) avec **retry+backoff** sur 429/5xx,
mode dégradé si aucune clé. Endpoints : `GET /api/llm/health|model-info`, **`POST /api/llm/chat`** (JWT **PARENT**).
Front : page **Assistant** (`/parent/assistant`, widget chat + suggestions). Delta MS10 : `GET /api/incidents/bus/{id}`
ouvert au **PARENT** (portée gardée par MS9) ; MS12 `/predict` ouvert au **PARENT**. **Validé e2e** (FR/AR/darija,
injection de prompt refusée, scope inter-parents refusé, écriture refusée). *(Clés Groq/Gemini gratuites sans CB dans
`ms9-llm/.env`, gitignoré.)*

**MS9 Phase B — NL2SQL admin ✅ livrée** (`admin_agent.py`, `db.py`, `POST /api/llm/admin/query`, JWT **ADMIN**) :
question en langage naturel → SQL PostgreSQL (schéma DDL injecté au prompt) → exécution → synthèse.
**Défense en profondeur, pas un simple garde applicatif** : connexion par un rôle Postgres dédié
**`ms9_readonly`** (droits en lecture seule accordés au niveau de la base) **et** exécution dans une
transaction `READ ONLY`, résultats capés. Un `DROP` généré par le modèle échouerait donc côté serveur,
même si le garde applicatif était contourné. Front : page **`AdminAssistant.tsx`** (`/admin/assistant`),
qui affiche la réponse, **le SQL généré** et le tableau de résultats.

---

**NOUVEAU (27/07) — App mobile PARENT Flutter (`frontend/parent-mobile/`, Flutter 3.44 / Dart 3.12) :**
Vraie app parent multiplateforme (cible dev **Chrome web** `:5174`, code Android-ready) qui **reprend à
l'identique les 5 écrans de l'espace parent web** en consommant le **même backend** (Gateway `:8080` + WebSocket
GPS direct `:8083`). *(Livrée sans delta backend ; depuis le 19/08 elle consomme 2 endpoints ajoutés
pour l'ETA — `/api/trajets/bus/{id}/route` et `/api/planification/mes-enfants`, cf. plus bas.)*
- **Écrans** (6) : Login · **Mon espace** (enfants/présence/bus + **compte à rebours** ETA gaté sur trajet démarré) ·
  **Carte de mon enfant** (`flutter_map` OSM/CARTO, bus filtrés aux enfants, **glisse interpolée** entre pings GPS,
  tuiles sombres) · **ETA / Prévisions** (`eta_screen.dart` : sens matin/soir + heure de départ → heure de passage
  estimée par enfant, ← **NOUVEAU 19/08**) · **Messagerie** (réception diffusions, poll 15 s) · **Notifications**
  (poll 15 s) · **Assistant** (chat MS9 `POST /api/llm/chat`) + badge non-lus (poll 20 s).
- **Archi** : `dio` (Bearer + 401→logout, timeouts 20 s / 120 s pour ETA+LLM), `web_socket_channel` (auto-reconnect
  2,5 s + throttle 1 s), `flutter_secure_storage` (JWT), `flutter_riverpod` (auth/enfants/GPS partagés), `intl`.
- **UI/UX + perf** (skill `flutter-ui-ux`) : **Material 3 thème pro clair + sombre** (toggle), tokens 4/8 pt,
  skeletons shimmer, countdown animé, `RepaintBoundary`, `const`, `ListView.builder`+keys, animations isolées + dispose.
- **Config réseau multi-cible (sans jamais toucher au code)** : un fichier JSON par environnement dans
  `config/` (`env.chrome.json` → `localhost`, `env.phone.json` → IP LAN), injecté via
  **`--dart-define-from-file`**. Si l'IP du PC change, **seul le JSON est à éditer**. Pour le téléphone :
  pare-feu 8080/8083 + `usesCleartextTraffic` (déjà dans le Manifest).
- **Lancement** :
  ```bash
  cd frontend/parent-mobile
  flutter run -d chrome --web-port 5174 --dart-define-from-file=config/env.chrome.json  # navigateur
  flutter run --dart-define-from-file=config/env.phone.json                              # téléphone
  ```
  Ou **en 1 clic** depuis VS Code (`.vscode/launch.json`) : « Parent App — Chrome » / « — Téléphone ».
- **Icône & branding** : icône bus sur dégradé bleu générée par `tool/generate_icon.py` (Pillow) puis
  déclinée par `flutter_launcher_icons` (Android + web) ; titre/manifest web personnalisés.
- **Qualité** : `flutter analyze` **0 issue** · `flutter test` **5/5** (login : rendu, validation, toggle
  mot de passe, thème sombre) · `Semantics` sur tuiles stats, cartes enfants, listes, pastilles carte.
- **Builds validés** : `flutter build web --release` ✅ · `flutter build apk --release` ✅ (**51,5 Mo**).
- ⚠️ **Correctif build Android (`dependency_overrides` dans `pubspec.yaml`)** : le projet utilise
  **AGP 9.0.1 / Gradle 9.1 / Kotlin 2.3.20**. `path_provider_android ≥ 2.3` (tiré transitivement par
  `flutter_secure_storage` → `…_windows` → `path_provider`) embarque le package **`jni`**, dont le
  `android/build.gradle` appelle l'ancienne méthode Groovy `kotlin()` → `assembleRelease` échoue avec
  *« Could not find method kotlin() on project ':jni' »*. **Solution : épingler `path_provider_android: 2.2.17`**
  (même service, sans `jni`). À retirer quand `jni` sera compatible AGP 9. *(N'affecte pas la cible web.)*
- **Skills Flutter installées** (`.claude/skills/` + `.claude/agents/`) : `flutter-ui-ux`, `flutter-tester`, agent `flutter-expert`.

---

**NOUVEAU (19/08) — ETA « le long de la tournée » + page Prévisions parent + migration LLM :**

**1. Correction de fond de l'ETA (5 écrans).** Symptôme : le compte à rebours *augmentait* (3→4→7→9 min),
même une fois l'enfant monté. Cause : l'ETA visait un point (école ou domicile) en **distance directe**, or la
tournée boucle `école → élèves → école` — pendant le ramassage le bus **s'éloigne** de l'école, donc la distance
directe croît alors que le bus avance normalement. *(Un premier correctif avait changé la **cible** selon la
présence ; insuffisant, le problème était le **chemin**.)*
- **Primitive partagée** : `web-admin/src/lib/routeEta.ts` + `parent-mobile/lib/services/route_eta.dart`
  (jumeaux, **parité vérifiée à 4 décimales**). Projette la position GPS sur la polyligne figée du trajet et
  mesure la **distance restante SUR le circuit** — quantité qui décroît. Cible `"fin"` pour l'école (la boucle y
  revient : viser ses coordonnées projetterait sur le **départ**), sinon le domicile cherché **devant** le bus.
  Vitesse déduite des totaux OSRM du circuit. **11 tests** (`test/route_eta_test.dart`).
- **Règle unique partout** : pas encore à bord → *chez vous* · à bord le matin → *l'école* · le soir → *chez vous*.
- Appliqué à `ChauffeurHome` (KPI « Arrivée école » → **« Fin de tournée »**, arrêts restants inclus),
  `ParentHome`, `ParentCarte`, `home_screen.dart`, `map_screen.dart`. Repli point-à-point si pas de tournée.

**2. Deltas backend liés :**
- **MS1** : `Trajet` + colonnes `distancePlanM` / `dureePlanMin` (totaux OSRM figés au démarrage → vitesse réelle
  du circuit, même calcul pour le chauffeur ET le parent) ; DTO `TrajetRouteResponse` ;
  **`GET /api/trajets/bus/{id}/route`** (ADMIN/CHAUFFEUR/**PARENT**) → polyligne + totaux, séparé de
  `/actif` car la géométrie pèse des dizaines de Ko et `/actif` est sondé toutes les 15 s. `groupeId` ajouté à
  `TrajetResponse`. *(Colonnes **nullables** → `ddl-auto=update` les crée seul, pas de migration manuelle.)*
- **MS5** : `planner.planifier()` renvoie `etapes` (cumul distance/durée **depuis l'école** à chaque arrêt) ;
  **`POST /api/planification/mes-enfants?sens=`** réservé au rôle **PARENT**, **portée imposée par le JWT**
  (`parentId` du token, jamais de la requête). MS5 planifie la tournée entière (nécessaire au cumul) mais ne
  renvoie **que** les étapes des enfants du demandeur — aucun autre nom/domicile/rang. `/tournee` et `/tournees`
  restent **interdits au PARENT** (une tournée = les adresses de toutes les familles du bus).
- **MS12 — garde anti-extrapolation** (`model.py::predire_minutes`) : le modèle a été entraîné sur des **tronçons**
  (0,7–4 km) ; une tournée restante atteint ~12 km. Hors domaine, on **n'extrapole plus** : le modèle est interrogé
  sur un tronçon **de référence** (médiane d'entraînement) avec le **contexte réel du moment** → **facteur
  d'inflation** (×1,32 fluide … ×2,36 embouteillage+pluie) appliqué à la durée OSRM restante. *Le ML dit de combien
  ça se dégrade aujourd'hui, OSRM dit la distance.* → **artefact gelé et métriques publiées (MAE 1,32 min,
  +52,7 %) restent valides**. Bornes gelées dans `eta_config.json` (`domaine_entrainement`, écrites par `train.py`) ;
  champ `mode_eta` (`modele_direct` | `facteur_contexte`) dans la réponse. Discontinuité mesurée à la bascule :
  **14,5 s**, soit 18 % du MAE du modèle → assumée.

**3. Page « Prévisions » parent (web + mobile)** — même principe que `/chauffeur/eta`, limité à ses enfants :
sens matin/soir + heure de départ de l'école → **heure de passage estimée** par enfant, rang (« 7ᵉ arrêt sur 50 »),
bus, km depuis l'école. Le cumul MS5 est passé à MS12 en `distance_routiere_m`/`duree_base_s` (donc via la garde
ci-dessus). Web : `ParentEta.tsx` → `/parent/eta` + entrée de nav. Mobile : `eta_screen.dart` → 6ᵉ onglet « ETA ».

**4. Présence figée dans l'UI (bug)** : `ChauffeurHome` et `useMyChildren` (parent web ×2) chargeaient les élèves
**une seule fois**. Une présence changée ailleurs (simulateur, admin, autre appareil) restait invisible jusqu'au
rechargement — seuls les pointages faits sur place s'affichaient (mise à jour optimiste). Sondage silencieux
ajouté (chauffeur 10 s en **préservant un pointage en vol**, parent 20 s via `usePolling`). Corrige au passage le
« recalcul immédiat à la montée » de l'ETA, qui ne pouvait jamais se déclencher côté web.

**5. Simulateur** : `bus_simulator.py` suivait déjà l'ordre MS5 et les vraies routes OSRM — **mais** si
`ordrePassage` était NULL (MS5 jamais lancé), `ORDER BY ordrePassage ASC` laissait un ordre arbitraire et le bus
zigzaguait **en silence**. `assurer_ordre_optimise()` détecte le cas, appelle MS5 (`persister=true`), relit l'ordre
et affiche le gain. Flag **`--optimiser`** pour forcer le recalcul.

**6. Page de connexion — refonte + 2 bugs.**
- **Bug thème sombre** : `--header` est une **encre de titre** (elle s'éclaircit en sombre : `#cdd8ea`) mais était
  utilisée comme **fond** sous du texte blanc → blanc sur clair, illisible. 4 endroits touchés (`Login`,
  `AppLayout`, `ChauffeurEta`, `EtaPrevisions`). Nouveau token **`--surface-deep`** (fond de marque, **toujours
  foncé**, contenu blanc ; contraste 14,3:1).
- **Bug thème non appliqué** : `useTheme` ne pose `[data-theme]` que depuis les écrans qui l'appellent (via
  `AppLayout`) → `/login` s'affichait en clair malgré un choix « sombre ». Thème désormais appliqué dans
  `main.tsx` **avant le premier rendu** (supprime aussi le flash).
- **Refonte** (skills `frontend-design` + `web-design-guidelines`) : volet gauche = **diagramme de réseau animé**
  (géométrie de plan de métro 0°/45°/90°) où **la tournée se résout** au chargement, lignes voisines convergeant
  vers l'école ; légende = le **vrai pipeline** (Regroupement MS6 → Tournée MS5 → Arrivée MS12). Décor **hissé hors
  du composant** (ne re-rend pas à la saisie), 100 % CSS, `prefers-reduced-motion` respecté.
- Qualité : `Admin123!` n'est plus pré-rempli qu'en `import.meta.env.DEV` (il partait dans le bundle de prod),
  `outline-none` retiré (il masquait l'anneau `:focus-visible`), `name`/`spellCheck`/`inputMode`, `aria-hidden`
  sur les icônes, bascule d'affichage du mot de passe.

**7. MS9 — migration LLM forcée (⚠️ modèles décommissionnés)** : Groq a retiré **toute la famille Llama** le
**16/08/2026**. L'avis ne citait que `llama-3.3-70b-versatile`, mais `llama-3.1-8b-instant` a disparu **aussi** →
les 2 étages Groq de la cascade échouaient, MS9 retombait silencieusement sur Gemini.
- Nouvelle cascade : **`openai/gpt-oss-120b` → `openai/gpt-oss-20b` → Gemini** (`config.py` **et** `ms9-llm/.env`,
  qui a priorité et réintroduisait le modèle mort).
- `qwen/qwen3.6-27b` (2ᵉ modèle conseillé par Groq) **écarté** : n'a pas appelé l'outil au test — rédhibitoire
  pour un agent tool-calling. `gpt-oss` 120b et 20b : tool calling **vérifié**.
- **Bug latent corrigé** : `gpt-oss` renvoie un champ propriétaire **`reasoning`** et **aucun `content`** quand il
  appelle un outil ; `agent.py` réinjectait le message **brut** dans l'historique. Toléré par Groq, mais la cascade
  peut basculer sur **Gemini en cours de conversation** avec cet historique. `_assistant_spec()` réduit le message
  à `role`/`content`/`tool_calls` (et cesse de repayer les jetons de raisonnement à chaque tour).
- ⚠️ `max_tokens: 800` est **partagé avec les jetons de raisonnement** de `gpt-oss` → réponse visible
  potentiellement tronquée sur un tour multi-outils. À surveiller (monter à ~1200 ou brider `reasoning_effort`).

> **Vérifications** : `bun run build` (typecheck) ✅ · `flutter analyze` 0 issue ✅ · `flutter test` **16/16** ✅ ·
> `mvn compile` ms1 ✅ · `py_compile` MS5/MS12 ✅ · boucle tool-calling MS9 rejouée en réel ✅.
> **Non vérifié** : exécution complète (backend éteint). **MS1, MS5, MS12 et MS9 doivent être redémarrés.**
> Le chauffeur doit **démarrer un nouveau trajet** pour que les totaux OSRM soient persistés (un trajet déjà en
> cours reste route-aware mais retombe sur la vitesse urbaine par défaut).

---

**NOUVEAU (20/08) — App mobile CHAUFFEUR Flutter (`frontend/chauffeur-mobile/`, Chrome `:5175` / Android) :**
Miroir mobile de l'espace chauffeur web (7 écrans), construite sur l'architecture de `parent-mobile`.
**Différence de nature : cette app ÉCRIT** (démarrer/terminer un trajet, pointer les présences, signaler un
incident, écrire à l'administration, diffuser aux parents) et **émet la position GPS réelle du bus**.

- **Écrans (7 + login)** — barre basse **Tournée · Carte · Messages · Incidents · Plus** (Material 3 plafonne à
  5 destinations ; « Plus » ouvre une feuille avec **Prévisions ETA · Notifications · Historique · Thème ·
  Déconnexion** — les trois écrans qu'on consulte à l'arrêt, pas au volant).
- **Le téléphone est la source GPS** (`POST /api/gps/position`, déjà ouvert au rôle CHAUFFEUR côté MS3 → **aucun
  delta backend**). Interrupteur « Transmettre ma position », **OFF par défaut** (sinon le téléphone et
  `bus_simulator.py` se disputent le même bus) ; n'émet que **pendant un trajet** ; 1 envoi / 5 s, filtre 15 m.
  ⚠️ **Conversion m/s → km/h obligatoire** : `geolocator` renvoie des m/s, `bus_simulator.py` publie des **km/h**
  (40 normal, 110 pour déclencher l'anomalie, seuil MS11 = 90). Sans elle, la vitesse serait 3,6× trop faible et
  `VITESSE_EXCESSIVE` ne se déclencherait jamais depuis un vrai téléphone.
  Émission écran verrouillé via le **`ForegroundNotificationConfig` de geolocator** (service de premier plan lié au
  flux) → **pas de `ACCESS_BACKGROUND_LOCATION`**, pas de second isolate. *(`flutter_foreground_task` écarté : il
  aurait imposé de recréer Dio et le JWT dans un autre isolate pour le même résultat.)*
- **File d'écritures hors ligne** (`lib/services/outbox.dart`) — **FIFO strict, single-flight**, persistée en JSON
  dans `shared_preferences` (choisi contre sqflite (KO sur le web) et hive (codegen) ; surtout **ne tire pas
  `path_provider`**, donc reste à l'écart du piège `jni`/AGP 9). Déclencheurs : `connectivity_plus`, reprise
  d'app, balayage 30 s. Sémantique **par type d'écriture**, c'est le cœur du sujet :
  · `presence` — valeur absolue (`?present=`) donc idempotente → deux pointages du même élève sont **fusionnés** ;
  · `trajetDemarrer` — **non idempotent** (MS1 `TrajetService.demarrer` lève si un trajet est déjà `EN_COURS`) →
    sur refus, on lit `GET /api/trajets/mon-actif` et on **adopte** le trajet existant (réconciliation, pas retry) ;
  · `trajetTerminer` — idem via `mon-actif` (plus de trajet actif ⇒ déjà clos) ;
  · `incident` / `message` / `diffusion` — **aucune clé d'idempotence côté serveur** → at-least-once assumé,
    plafond **3 essais** puis l'item est « parké » et la décision revient au chauffeur (réessayer / abandonner).
  **Les positions GPS ne sont PAS rejouées** : `PositionRequest` n'a pas d'horodatage (MS3 date à la réception),
  réémettre un point vieux de 3 min écrirait une **fausse position courante**.
- **Démarrer hors ligne est refusé sans itinéraire en cache** (`tournee_cache.dart`, clé `(groupeId, sens)`) :
  démarrer sans `geometrie` prive MS11 de sa référence et **désarme la détection de déviation en silence**.
  Le bouton est désactivé et la raison affichée, plutôt que de partir à l'aveugle.
- **Testabilité — le point faible de `parent-mobile` corrigé** : `Api.instance` (singleton) est remplacé par une
  interface **`ApiClient`** derrière `apiProvider`, `Outbox` derrière `outboxProvider` avec un `MemoryOutboxStore`.
  **55 tests** : `route_eta` 11 (copiés, garantissent la parité avec le jumeau parent), `outbox` 11 (ordre,
  fusion, réconciliation, plafond, persistance après kill), `login` 7 (dont **rejet d'un compte PARENT**),
  `tournee` 12 (dont **le démarrage envoie bien `groupeId` ET `geometrie`**, rollback sur refus serveur, mise en
  file hors ligne), `messages` 8, `incidents` 6.
  *Un test a révélé un vrai bug* : le `TextEditingController` de la diffusion était libéré pendant l'animation de
  fermeture de la feuille → « used after being disposed ». Corrigé (contrôleur porté par l'état).
- **Écarts assumés vs la console web** : (1) l'écran **Prévisions ETA** part du **cumul MS5 depuis l'école** passé
  à MS12 (comme la page parent) au lieu des N appels tronçon-par-tronçon du web — deux méthodes donneraient deux
  heures différentes pour le même enfant, on s'aligne sur ce que voient les familles ; concurrence bornée à 6
  appels pour ne pas heurter le rate-limiter Gateway (20 req/s). (2) Quand un trajet est en cours, l'ETA et la
  carte utilisent la polyligne **figée par MS1** (`/api/trajets/bus/{id}/route`), celle que MS11 surveille et que
  l'app parent utilise, plutôt qu'une tournée re-planifiée.
- **Socle dupliqué depuis `parent-mobile`** (theme, common, env, auth_store, gps_socket, **route_eta + ses 11
  tests**, generate_icon) plutôt qu'extrait en package partagé : l'app parent est **livrée et validée** à
  quelques semaines de la soutenance. Garde-fou contre la divergence : les tests de parité sont copiés aussi.
  Clé de session distincte (`ts_auth_chauffeur`) et **icône teal** (`#0F766E`) pour la cohabitation des deux apps
  sur un même téléphone.
- **Aucun delta backend.** Seuls `.vscode/launch.json` (3 entrées, `--web-port=5175`) et `.gitignore`
  (exceptions PNG symétriques) sont touchés hors du nouveau dossier.

> **Vérifié hors ligne** : `flutter analyze` **0 issue** ✅ · `flutter test` **68/68** ✅ ·
> `flutter build web --release` ✅ · `flutter build apk --release` ✅ (**54,3 Mo** — confirme que
> `path_provider_android: 2.2.17` + `geolocator` passent AGP 9) · non-régression `parent-mobile` : 16/16 ✅.

> **Vérifié CONTRE LE BACKEND RÉEL (20/08, tous MS + OSRM up)** — les 12 contrats consommés par l'app,
> validés champ par champ contre les modèles Dart :
> · `POST /api/auth/login` (CHAUFFEUR, JWT `userId`/`role`) · `GET /api/bus` (10 bus, 1 au chauffeur 32)
> · `GET /api/eleves/bus/14` (50 élèves, `ordrePassage` 1..50) · `/api/trajets/{mon-actif,mes-trajets,bus/14/route}`
> · `POST /api/planification/tournee` (50 arrêts, 882 pts, `etapes` conformes à `EtapeTournee`)
> · `POST /api/eta/predict` dans les 3 modes (`mode_eta` = `facteur_contexte` à 12 km, `modele_direct` à 2 km)
> · `/api/incidents/bus/14`, `/api/messages/{ma-conversation,non-lus}`, `/api/notifications/mes-notifications`.
> **Cycle de trajet complet joué** : clôture → `POST /demarrer` avec le payload exact de l'app → **HTTP 201**
> → `GET /route` renvoie **882 points + totaux figés** ⇒ *surveillance de déviation MS11 armée* (c'était LE
> point non vérifié). **Non-idempotence confirmée en réel** : un second démarrage renvoie
> `400 « Un trajet est déjà en cours pour ce bus (id=18) »` — exactement le cas que la file réconcilie via
> `mon-actif`. **`POST /api/gps/position` en CHAUFFEUR accepté**, 43,2 km/h persistés ; MS11 `/live` expose
> `seuils.vitesse_kmh = 90` ⇒ **la conversion m/s→km/h est indispensable et correcte**.
> **NON vérifié** : émission GPS depuis un téléphone physique, tenue du service de premier plan au-delà de
> quelques minutes écran verrouillé (et survie au *Doze* constructeur), batterie, iOS (pas de cible iOS).

> **Campagne de correction du 22/08 — vérifications** : `flutter analyze` 0 issue sur les deux apps ·
> `flutter test` **84/84** (chauffeur) et **25/25** (parent) · `bun run build` (web-admin) ✅.
> **Contre le backend réel** : MS5 rechargé → convergence `distance_m` / longueur de `geometrie` à **0,05 %** ;
> nouveau trajet démarré avec le payload de l'app → MS1 persiste **753 pts + totaux** ; **déviation forcée →
> `DEVIATION_ITINERAIRE` détectée** (écart 277,2 m, seuil 250 m) ⇒ la surveillance MS11 reste opérationnelle
> après le changement de géométrie.
> **La primitive ETA est vérifiée dans ses 3 implémentations sur la MÊME tournée réelle** — les deux apps Dart
> par `route_eta_reel_test.dart` (fixture `test/fixtures/tournee_groupe1.json`, 753 points), et le TypeScript
> par un script `bun` jetable exécutant `routeEta.ts` sur la même fixture. Résultats identiques :
> 99 % du parcours → **35,4 min avant / 0,6 min après**, et au départ l'ETA vaut **35,99 min**, exactement la
> durée annoncée par MS5 (preuve que la vitesse est bien dérivée de la polyligne mesurée).
> ⚠️ `web-admin` n'a **toujours aucun lanceur de tests** : hors cette vérification ponctuelle, ses corrections
> ne sont couvertes que par le typecheck.

---

**NOUVEAU (23/08) — Campagne de benchmark des 4 briques IA restantes, sur le modèle du CVRP.**
La méthode du benchmark CVRP (question réversible · challenger crédible · protocole égalisé · métriques
opérationnelles · incertitude énoncée · verdict écrit + perdant reclassé) a été **généralisée aux cinq
briques**, et formalisée dans **`docs/PROTOCOLE_BENCHMARK_IA.md`** — le document méthodologique du mémoire.

**Le défaut structurel qu'elle a révélé, commun à trois briques : *ce qui tournait en production n'était
pas ce qui avait été benchmarké*.** MS6 comparait dix algorithmes euclidiens sans que le k-médoïdes
capacitaire **routier** déployé y figure ; MS11 benchmarkait l'Isolation Forest (à la demande) pendant que
les **règles live** (sur chaque ping GPS) n'avaient aucune métrique ; MS12 publiait des métriques de
tronçons alors que le service tourne en mode **`facteur_contexte`** sur 6–12 km.

- **MS6** (`ablation_distance.py`, `docs/MS6_BENCHMARK_DISTANCE.md`) — l'algorithme de production entre dans
  l'arène, avec deux baselines naïves absentes du dossier. **Ablation propre** (un seul facteur : la matrice) :
  la distance routière vaut **+0,002 de silhouette (invisible)**, **−1,5 % de conduite** et surtout
  **−1,7 min de temps à bord par enfant (−9,7 %)**. « Un bus par quartier » coûte **+14,6 %** ; aléatoire
  **+110 %** ; refuser l'infaisable coûte **3,4 %**. ⚠️ **Silhouette et minutes désignent deux gagnants
  différents** (k-means capacitaire est meilleur en flotte, moins bon à bord) → il faut choisir la métrique
  avant de comparer. Variance 10 graines : k=7 stable (±0,0001), k=8 (±0,0119) et k=9 (±0,0204) non.
  ⚠️ **Correction du 24/08** : ce bilan affirmait initialement que le pipeline produisait **k=8** contre
  **k=7** dans la config gelée, et y voyait une incohérence. **C'était faux** — le service produit bien
  k=7. Le benchmark appelait la bonne fonction avec les élèves **triés par id (CSV)** alors que le service
  les reçoit dans l'ordre du tas PostgreSQL. Le vrai défaut est **pire** : voir piège n° 19.
- **MS11** (`replay.py`, `ablation_anomaly.py`, `docs/MS11_BENCHMARK_REGLES_LIVE.md`) — rejeu hors ligne des
  règles live sur la **vraie tournée de 753 points**. **La règle de déviation est largement aveugle** : un
  détour de 250 m n'est vu que sur **9,6 % du parcours**, 400 m sur 35,8 % — parce qu'elle mesure la distance
  au point le plus proche de **toute** la polyligne, et qu'une tournée de 50 arrêts repasse dans le même
  quartier (**c'est le piège n° 13, le cycle fermé, jamais corrigé ici**). Abaisser le seuil à ~120 m
  doublerait la couverture **sans aucune fausse alarme mesurée** (jusqu'à σ=30 m de bruit GPS). L'anti-rebond
  à 2 pings est **optimal** (−3,34 fausses alarmes/h pour +5 s) — mais `VITESSE_EXCESSIVE` n'en a aucun.
  **Et le classement ML s'inverse** : sous validation glissante (38 positifs au lieu de 8), `seuil_surprise`
  (0,926) **bat** `iforest_curated` (0,847). La thèse « le seuil rate le contextuel » est **fausse** — c'est
  l'inverse (12/14 contre 3/14) ; l'IF n'apporte en propre que la **surcharge** (7/7 contre 3/7).
  La **fuite** générateur→feature soupçonnée **n'existe pas** : coefficients ré-estimés depuis les données
  → +0,003 de PR-AUC.
- **MS12** (`ablation.py`, `docs/MS12_BENCHMARK_GARDE_ET_ABLATION.md`) — **la garde `facteur_contexte` est
  validée** sur trajets entiers (6,4–11,8 km, agrégés depuis le dataset sans rien inventer) : MAE **2,17 min**
  contre **3,45** en extrapolant (**−37 %**) et **9,33** pour OSRM brut (**−77 %**). L'écart ElasticNet/Ridge
  de 2,7 s **est significatif** (bootstrap apparié) — contrairement à ce qu'on supposait — et tient **après
  réglage** de XGBoost (1,6729 → 1,3945, toujours derrière 1,3219). Baseline manquante ajoutée : la moyenne
  historique donne 1,52 → le gain réel est **44 %**, pas 52,7 %. **Biais constant de +0,515 min** : le
  corriger fait gagner **−14,6 % de MAE**. Ablation : météo+trafic portent tout (+0,48), Ramadan+souk valent
  **+0,10**, et **`dwell` + `temporel` sont nuisibles** (le modèle ferait mieux avec 10 features de moins).
  ⚠️ `domaine_entrainement` vaut **`null`** dans `eta_config.json` : sans le CSV au démarrage, la garde se
  **désarme en silence**.
- **MS9** (`tests/test_sql_guard.py`, `eval/`, `docs/MS9_EVALUATION.md`) — la brique passe de **zéro artefact
  d'évaluation** à un jeu de test **versionné et rejouable**. Corpus `sql_guard` de 29 cas : **14/14 attaques
  bloquées**, 8/8 requêtes légitimes préservées, **4 contournements délibérément déférés à PostgreSQL**
  (`SELECT *`, catalogues `pg_user`, `LIMIT` imbriqué, produit cartésien) et **3 faux positifs** chiffrés.
  Golden set parent de 36 questions (fr/ar/darija × opérationnelle/école/hors-sujet/injection/hors-portée/
  écriture) rejoué **sur chaque modèle** avec la cascade **neutralisée**.
  **Résultats** : `gpt-oss-120b` **100 %** sur les 4 critères ; `gpt-oss-20b` 88,2 % (il se dégrade
  **spécifiquement en darija** : il redemande de quel enfant il s'agit au lieu de répondre) ;
  `qwen3.6-27b` **16 réponses vides sur 36** — l'écarter était juste, c'est désormais mesuré ;
  `gemini-flash-latest` correct mais **7× plus lent** (p50 11,1 s) et limité à 10/36 par son quota.
  **⚠️ Panne de production trouvée** : `gemini-2.0-flash`, 3ᵉ et dernier étage du repli, répond
  **404 sur 36/36** — le modèle n'est plus servi (cf. piège n° 7). MS9 n'avait plus aucun repli.
  **NL2SQL** : **83,3 % d'exactitude d'exécution stricte / 94,4 % en tolérant les colonnes
  supplémentaires**, **0 fuite sur 6 attaques** — mais les couches profondes (`sql_guard`, rôle
  Postgres) **ne sont jamais atteintes** : le modèle refuse avant. La défense en profondeur reste
  justifiée précisément parce qu'on ne peut pas compter sur la docilité d'un modèle.

> **Nature des livrables** : tout est **additif** — un module isolé et un document par brique, aucun fichier
> de production modifié. Les défauts trouvés sont **rapportés, pas corrigés** (décision de production).
> Dépendances installées pour la campagne : `pyproj`, `ortools`, `k-means-constrained`, `xgboost`, `lightgbm`.

---

**NOUVEAU (25/08) — MS13 ParametreService : la configuration devient pilotable depuis `/settings`.**

Avant : **aucun paramètre métier n'était modifiable sans éditer du code**. `/settings` n'écrivait que
`{capacity, rayon}` dans le `localStorage` du navigateur, et tout le reste vivait dans un `.env` ou une
constante compilée. Trois conséquences déjà payées : les coordonnées de l'école écrites à **6 endroits**
(dont **MS4 en désaccord de ~900 m** avec les cinq autres), les correctifs mesurés au benchmark
inapplicables sans redémarrage, et deux pannes de modèle LLM qui ont exigé d'éditer `.env` puis relancer.

**Service `ms13-parametres/` (Spring Boot :8092)** — source de vérité unique, **60 réglages** sur
9 onglets. Le **catalogue est du code** (`ParametreCatalogue.java`) : au démarrage, un *upsert non
destructif* réécrit les métadonnées (libellé, bornes, défaut) et **ne touche jamais les valeurs**.
Ajouter un réglage = une ligne, aucune migration. *(Vérifié : au 2ᵉ démarrage, « 0 créés, 60 mis à jour ».)*
- `GET /api/parametres` (tout rôle, **secrets masqués**) · `GET /schema` (ADMIN) · `PUT` (ADMIN, lot
  **validé en bloc** : une valeur refusée ⇒ rien n'est écrit) · `POST /reset` · **`GET /internal`**
  (valeurs **en clair**, **non routée par la passerelle** — motif déjà retenu pour MS4→MS2).
- **Propagation à chaud** : `parametres.updated` (RabbitMQ, `text/plain`) + relecture périodique en
  filet + lecture au démarrage. Le message ne porte **que les clés changées** ; chacun relit la source,
  donc un message perdu ou réordonné ne peut pas désynchroniser deux services — et **aucun secret ne
  transite par le bus**.
- **Consommateurs** : `params.py` **dupliqué à l'identique** dans MS5/6/9/11/12 (machinerie vérifiée
  par empreinte MD5 ; seul le `MAPPING` diffère) et `ParametresCache.java` dans MS4. Muter le singleton
  pydantic suffit : ces services lisent `settings.x` **au moment de l'appel**, jamais à l'import.
- **Front** : `ParamsContext` (web-admin, 3 espaces) remplace `lib/prefs.ts` (supprimé) et **~20
  intervalles en dur**. `Settings.tsx` réécrite : onglets et champs **entièrement pilotés par `/schema`**,
  aucun libellé en dur. **Flutter** : `params_service.dart` alimente `Env`, dont les `static const`
  deviennent des accesseurs — **aucun site d'appel modifié**, les constantes restent le repli hors ligne.

**Deltas de production livrés avec** :
- **MS4** : les constantes `ECOLE_LAT/LNG/RAYON_METRES` disparaissent → **la divergence de 900 m est
  corrigée** ; 5 interrupteurs de notification.
- **MS12 — contexte `auto | manuel`** : l'administration peut **imposer** météo, trafic, ramadan, souk et
  travaux au lieu des sources automatiques. Le champ `sources` de la réponse porte alors
  `"manuel (admin)"`. *Mesuré en réel : pluie + embouteillage + travaux contre beau + fluide = **×2,25**
  sur le même tronçon.* Utile quand Open-Meteo est injoignable, quand l'exploitant sait ce que les
  sources ignorent, et pour démontrer l'effet du contexte sans attendre qu'il pleuve.
- **MS11** : **anti-rebond de `VITESSE_EXCESSIVE`** (`vitesse_pings_consecutifs`, défaut **1** = comportement
  historique) — comble le manque du piège n° 17. `/live` publie désormais les 6 seuils, ce qui rend la
  propagation vérifiable de l'extérieur.
- **MS6** : interrupteur `recalcul_auto` (couper le recalcul RabbitMQ pendant une campagne d'inscriptions,
  cf. piège n° 19) — le message est **consommé et acquitté**, pas accumulé.
- **MS9** : **`GET /api/llm/admin/models-check`** — confronte la cascade configurée à ce que servent
  réellement les fournisseurs. C'est la vérification que le CLAUDE.md réclamait avant chaque démo.

> **Vérifié contre le backend réel** : MS13 **25/25** (validation, bornes, énumérations, atomicité du lot,
> masquage, RBAC parent) · routage **9/9** (dont `GET /api/parametres/internal` via la passerelle → **404**,
> le test qui compte) · **propagation à chaud MS13→MS11 en 3,15 s sans redémarrage** · MS4 lit bien
> `33.893,-5.5455` · contexte manuel MS12 ×2,25 · `models-check` : `gemini-2.0-flash` **confirmé mort**
> (absent des 51 modèles servis), corrigé **à chaud** en `gemini-flash-latest` → verdict OK.
> `bun run build` ✅ (et **aucune clé ni route interne dans le bundle**) · `flutter analyze` 0 issue ×2 ·
> `flutter test` **93/93** (chauffeur, +9) et **33/33** (parent, +8) · `mvn compile` ✅.

> ⚠️ **Trois défauts trouvés *pendant* l'implémentation, par la vérification et non par la relecture** —
> ils valent d'être connus, les trois étaient silencieux :
> 1. **Renvoyer le masque détruisait la clé API.** Le formulaire reçoit `••••••4f2a` et le garde dans son
>    état ; modifier un autre champ de l'onglet renvoyait le masque, que le serveur écrivait
>    consciencieusement (**HTTP 200**). Garde ajoutée **côté serveur** (une valeur commençant par `•`
>    n'est jamais écrite), pas dans le formulaire : elle doit tenir quel que soit le client.
> 2. **Une valeur vide de MS13 écrasait un secret local.** Constaté en réel dans les journaux : MS9 a
>    remplacé ses clés Groq et Gemini — valides, lues de son `.env` — par des chaînes vides, parce que le
>    catalogue n'a pas de défaut pour un secret. L'assistant serait tombé au premier message. **Le `.env`
>    reste l'amorçage** : MS13 ne prend le dessus que lorsqu'il a effectivement une valeur.
> 3. **`models-check` déclarait tous les modèles Gemini morts.** Gemini renvoie `models/gemini-flash-latest`
>    quand on l'appelle avec `gemini-flash-latest` ; la comparaison exacte produisait une **fausse alerte** —
>    pire qu'aucune vérification, puisqu'elle aurait discrédité l'alerte le jour où elle est vraie.
>    Préfixe normalisé, et la distinction est vérifiée dans les deux sens.

> **Exclusions délibérées, à savoir défendre** : les paramètres de **génération de dataset**
> (`seed`, `n_jours`, `incident_rate`, `contamination`…) ne sont **pas** exposés — les artefacts ML sont
> gelés, les modifier depuis l'écran n'aurait aucun effet et **l'interface mentirait**. Idem pour les
> quotas de la passerelle (routes Spring Cloud non rechargeables à chaud), le `JWT_SECRET` et les mots de
> passe Postgres.

---

**NOUVEAU (25/08) — MS4 : le canal de notifications poussées est branché (lots 0-2 et 5).**
📄 **Document autonome : [`docs/MS4_NOTIFICATIONS_FCM.md`](docs/MS4_NOTIFICATIONS_FCM.md).**

Point de départ : la console affichait **10 157 notifications sur 10 157 en ECHEC**, motif unique
« Aucun device FCM enregistré ». Diagnostic : `device_tokens` contenait **2 lignes, 0 active**, et
**aucun client n'appelait `POST /device-token`** — ni le web-admin, ni les deux applications Flutter,
dont aucun `pubspec.yaml` ne déclarait Firebase. Le canal push n'avait **jamais** été raccordé.
Firebase côté serveur, lui, était correctement configuré depuis l'origine.

**L'échec de 100 % n'était pas la vraie nouvelle.** Les notifications in-app fonctionnaient
(`getMesNotifications` ne filtre pas le statut) ; `ECHEC` signifiait seulement « le téléphone n'a
pas sonné ». Le vrai défaut, c'est ce que cet échec **masquait** — quatre bugs qui se seraient tous
manifestés le jour du branchement :

- **Rafale `BUS_ARRIVE_ECOLE`** (**94 % du volume**, 9 546 lignes) : la règle notifiait à **chaque
  ping GPS** dans le rayon, or un bus stationné continue d'émettre. Mesuré : **150 notifications
  identiques par parent espacées de 1,2 s**, un parent à 210, **pic à 1 110 pour un bus en une
  minute**. Corrigé par un **verrou d'entrée de zone** (annonce au franchissement seulement) +
  **marge d'hystérésis `rayon × 1,5`** (sinon un bruit GPS de ±20 m fait clignoter l'alerte sur un
  bus immobile posé sur la frontière) + délai minimal MS13 `ms4.arrivee_ecole_cooldown_min` (30 min,
  `0` = verrou seul). **Le verrou est aussi posé à `trajet.demarre` sans notifier** : la tournée part
  de l'école, donc sans cela le premier ping annoncerait une « arrivée » au moment du départ — cas
  rejoué à chaque redémarrage de MS4.
- **Une ligne d'historique par appareil** (`sauvegarder` était *dans* la boucle d'envoi) : invisible
  à zéro appareil, mais un parent connecté sur trois origines aurait vu le message **en triple**.
  Sortie de la boucle → **une ligne par événement métier**, `ENVOYE` dès qu'un appareil a reçu.
- **Enregistrement non idempotent** : `fcm_token` porte une contrainte **UNIQUE**, et le code
  désactivait la ligne existante *sans la supprimer* avant d'en insérer une nouvelle avec le même
  jeton → **HTTP 500**. Comme un jeton FCM est **stable par installation**, *toute deuxième connexion
  depuis le même appareil échouait*. La ligne est désormais **réaffectée** (le jeton appartient à
  l'appareil, pas au compte).
- **Journal non paginé** : `GET /api/notifications` faisait un `findAll()` — plus de 10 000 lignes
  transportées à chaque sondage pour 25 affichées, sur une table qui grossit de 1 100 lignes/min en
  simulation. Pagination serveur (`page/size/tri/sens/adminSeulement`, tri en **liste blanche**), et
  le total des alertes admin vient maintenant de `/stats` puisque la page ne voit plus qu'une tranche.

**Deltas** : MS4 `FcmService`/`NotificationService`/`NotificationController` ; `/device-token` ouvert
au rôle **CHAUFFEUR** (il recevait déjà des notifications et lisait déjà `/mes-notifications` — seul
l'enregistrement restait fermé) ; plateforme normalisée, repli **`INCONNU`** et non `ANDROID`
(l'appel explicite du constructeur écrasait le `@Builder.Default`, un client web omettant le champ
s'enregistrait à `null`). MS13 : 1 paramètre. `parent-mobile` : `firebase_core`/`firebase_messaging`,
`web/firebase-messaging-sw.js`, `push_service.dart` (ne lève jamais, dépendances injectées,
réabonnement `onTokenRefresh`), câblé sur `login`/`logout` — **détachement avant l'effacement du
JWT**, l'appel étant authentifié.

> **Vérifié** : MS4 `mvn test` **17/17** (verrou 6 · FcmService 5 · DeviceToken 5 · contexte) ·
> `parent-mobile` `flutter analyze` **0 issue**, `flutter test` **38/38**, `build web` ✅,
> **`build apk --release` ✅ 53,4 Mo** · `web-admin` `bun run build` ✅.
> **Spike Gradle concluant** : `google-services` 4.3.15 passe sur **AGP 9.0.1 / Gradle 9.1 /
> Kotlin 2.3.20** sans échappatoire — mais Flutter avertit que **`firebase_core` applique KGP** et
> que *« future versions of Flutter will fail to build »* (cf. piège n° 25).
> **Non vérifié** : bout en bout réel (MS4 doit être redémarré), push sur téléphone physique,
> `web-admin` et `chauffeur-mobile` (lots 3 et 4, non faits).

**NOUVEAU (26/08) — Recette finale : la vérification de bout en bout avant le mémoire.**
📄 **Document autonome : [`docs/RECETTE_FINALE.md`](docs/RECETTE_FINALE.md) · scripts : `scripts/recette/`.**
📄 **Suite : [`docs/PLAN_CORRECTIONS.md`](docs/PLAN_CORRECTIONS.md)** — planning de correction en 7 lots.
> ⚠️ Une revue de code postérieure, ciblée sur les **interactions entre acteurs**, a trouvé
> **13 défauts de portée de plus** (IDOR) que la recette ne couvrait pas — dont `PATCH /presence`
> ouvert à tout chauffeur sur tout élève, la **polyligne de tournée** lisible par tout parent, et le
> **WebSocket GPS sans aucune authentification**. Registre consolidé : **33 défauts**.

Objet : non pas montrer que tout marche, mais **confronter chaque chiffre publié ici et dans le
`README.md` à ce que la stack fait réellement**. Huit phases, toutes rejouables
(`scripts
ecette	out.cmd offline|live`).

**Ce qui est confirmé, mesuré ce jour** : MS5 convergence `distance_m` ↔ géométrie à
**0,05 / 0,03 / 0,02 %** (piège 14) · **churn 0/301 élèves** au recalcul appliqué (piège 19) ·
masque MS13 non écrit et secrets du `.env` préservés (piège 21a/b) · **propagation à chaud
MS13→MS11 en 2,30 s** · verrou d'arrivée : bus garé, 30 pings → **26 notifications pour
27 parents** (piège 23) · jeton FCM réenregistré 3× → 200/200/200 (piège 24) ·
`models-check` **verdict OK**, les 3 modèles de la cascade réellement servis (piège 7) ·
limiteur de la passerelle **36 × 429 sur 40 connexions parallèles** ·
`GET :8080/api/parametres/internal` → **404** · **22 combinaisons rôle × route** correctes ·
**27 routes web-admin rendues, 0 erreur console, 0 requête en échec** dans un Chrome réel.

**Ce qui ne l'est pas — 20 défauts, dont 2 critiques (cf. pièges n° 28 à 31)** :
- 🔴 **auto-promotion ADMIN** par `POST /api/auth/register` (`role` lu dans le corps),
  **exploitable sur 6 surfaces d'administration sur 6**, NL2SQL compris ;
- 🔴 **`GET /api/eleves` est `permitAll`** : **301 élèves, nom, prénom et domicile GPS** servis
  sans authentification sur `:8082` — détecté par l'assertion Newman n° 13, jamais rejouée
  (**87/88**, pas 88/88) ;
- 🟠 aucun contrôle de propriété sur `/api/eleves/parent/{id}` et `/api/gps/eleve/{id}/historique` ;
- 🟠 `/carte` sans garde de rôle : un parent y voit **14 bus en direct + la flotte** ;
- 🟠 **un ADMIN ne peut pas clore un trajet** ⇒ bus bloqué sans recours (démarrage non idempotent) ;
- 🟡 **`mvn test` = 18 tests, pas 22** : 5 modules à `skipTests=true` ;
- 🟡 **28 944 messages** dans 7 files RabbitMQ **sans consommateur** (`gps.bus.updated.queue` : 28 918) ;
- 🟡 MS7 renvoie **401 au lieu de 403** (pas d'`accessDeniedHandler`) ⇒ le front **déconnecte** ;
- 🟡 déviation : couverture **re-mesurée sur 2 vraies tournées** — un détour de **300 m** n'est vu
  que sur **29,1 %** (groupe 1) et **16,3 %** (groupe 3) du parcours ; **plus la tournée est longue,
  plus la règle est aveugle** (constat nouveau vs piège 17) ;
- 🟡 la production tourne à **k=9 bus** quand `production_config.json` annonce **k=7** — c'est
  l'hystérésis qui fait son travail (churn 0 %), mais elle ancre le système sur une partition
  antérieure au correctif. **À trancher avant la soutenance** ;
- 🟡 MS12 `domaine_entrainement` **null** : la garde ne tient qu'au CSV présent au démarrage ;
- 🟡 le test G1 du e2e échoue de **3,6 s** sur son seuil (ETA 10,06 min contre 10) — la chaîne,
  elle, est prouvée : notification `BUS_EN_ROUTE` en **3 s** à 2 214 m.

> **Aucun défaut n'a été corrigé** — même discipline que la campagne de benchmark du 23/08 :
> rapportés, chiffrés, documentés ; la correction est une décision de production. Seuls les
> n° 1 et 2 sont signalés comme **à corriger avant toute démonstration publique**.
> **Nouveauté d'outillage** : `web-admin`, qui n'avait aucun test, dispose désormais d'un
> balayage Chrome (`scripts/recette/balayage_front.mjs`, `puppeteer-core`) qui exerce ses
> **27 routes × 3 rôles** avec captures d'écran ; et le « 88/88 » a enfin un lanceur.

---

**NOUVEAU (27/08) — Correction : les 15 failles de portée sont fermées, retour à 7 bus.**
📄 **Journal d'exécution : [`docs/JOURNAL_CORRECTIONS.md`](docs/JOURNAL_CORRECTIONS.md).**

Exécution des lots 0 à 4 du plan. **Tout est vérifié contre la stack vivante**, pas relu.

**Les deux bloquants** : `POST /api/auth/register` force désormais `PARENT` (le champ `role`
du corps est ignoré) ; `GET /api/eleves` exige un jeton, et les services sans jeton
utilisateur (MS5, MS6, MS12) passent par **`GET /internal/eleves`** — un préfixe
volontairement **hors** de `/api/eleves/**`, que la passerelle route en entier.

**Les 15 failles de portée** sont fermées par un `PorteeService` par service, alimenté par
deux nouvelles routes internes (`/internal/parents/{id}/bus` côté MS2,
`/internal/bus/chauffeur/{id}` côté MS1), toutes **en échec fermé**. Plus C1 (un ADMIN peut
enfin clore un trajet) et C2 (403 au lieu de 401 : le front ne déconnecte plus).

**Retour à k=7 bus** — la partition en place était tombée à **un groupe de 9 élèves** sur un
bus de 50 places pendant qu'un autre en portait 47. Après désarmement de l'hystérésis :
**50 · 44 · 42 · 37 · 50 · 48 · 29**, remplissage **67 % → 86 %**, verdict qualité **OK**,
silhouette 0,4256 (= l'ancre gelée). Deux bus et deux chauffeurs économisés.
Rejouable : `python scripts/recette/migration_k7.py`.

| Vérification | Avant | Après |
|---|---|---|
| `scenarios.py` (39 scénarios acteur↔acteur, **nouveau**) | 18/33 | **39/39** |
| `contrats.py` | 60/66 | **67/67** |
| Newman | 87/88 | **88/88** |
| Balayage Chrome (27 routes × 3 rôles) | 40/42 | **42/42** |

> ⚠️ **Reste ouvert, assumé** : le **WebSocket GPS sans authentification** (piège n° 32),
> les lots 5 et 6 du plan, et la faiblesse structurelle de la règle de déviation.

---

## 📁 Structure racine du projet

```
C:\Users\Anass\Desktop\SDIA\S9\PFE\transport-scolaire\
├── pom.xml                          ← Parent Maven multi-module
├── docker-compose.yml               ← PostgreSQL + Redis + RabbitMQ + pgAdmin
├── .env                             ← Variables d'environnement Docker
├── scripts/init.sql                 ← Init SQL PostgreSQL
├── osrm-data/                       ← Données OSM Maroc pré-processées (OSRM)
├── seed_eleves_meknes.py            ← Script seeding 300 élèves
├── seed_eleves_meknes.sql           ← SQL généré : 300 élèves Meknès
├── bus_simulator.py                 ← Simulateur v2 DATA-DRIVEN (vraies tournées OSRM, présence G5, anomalies G3)
├── frontend/
│   ├── web-admin/                   ← Console admin React 18 + Vite + TS + Bun + Tailwind v4 (port 5173) ← NOUVEAU
│   │   └── src/ (api · auth · components · hooks · layout · lib · pages)
│   ├── parent-mobile/               ← App mobile PARENT Flutter 3.44 (Chrome :5174 / Android) ← NOUVEAU (27/07)
│   │   ├── lib/ (config · models · api · services[+push_service] · state · screens · widgets)
│   │   └── web/firebase-messaging-sw.js  ← service worker FCM (obligatoire sur le web) ← 25/08
│   └── chauffeur-mobile/            ← App mobile CHAUFFEUR Flutter (Chrome :5175 / Android) ← NOUVEAU (20/08)
│       └── lib/ (api[api_client·dio_api] · models · services[outbox·gps_emitter·tournee_cache·route_eta]
│                 · state · screens · widgets) + test/ (55 tests, fake ApiClient)
├── ws-test/
│   ├── test-gps.html               ← Test WebSocket GPS MS3
│   ├── map-gps.html                ← Carte Leaflet temps réel (GPS + OSRM routes)
│   ├── test-incidents-notifications.html  ← Test flow MS10→MS4 ✅ validé
│   └── test_ms6.html               ← Test clustering MS6 (nouveau S7)
├── ms-common/                       ← Module partagé (JWT, UserPrincipal, Role)
├── ms1-bus/                         ← BusService (port 8081)
├── ms2-eleves/                      ← EleveService (port 8082)
├── ms3-localisation/                ← LocalisationService GPS + WebSocket (port 8083)
├── ms4-notifications/               ← NotificationService FCM (port 8084)
├── ms6-clustering/                  ← ClusteringService FastAPI Python (port 8086) ← NOUVEAU S7
├── ms7-auth/                        ← AuthService JWT (port 8087)
├── ms8-gateway/                     ← API Gateway Spring Cloud (port 8080)
└── ms10-incidents/                  ← IncidentService (port 8090)
```

---

## 🔧 Stack technique

| Catégorie | Technologie |
|-----------|------------|
| **Langage Java** | Java 21 |
| **Framework Java** | Spring Boot 3.5 |
| **Build** | Maven multi-module |
| **Gateway** | Spring Cloud Gateway WebFlux 2024.0.1 |
| **Base de données** | PostgreSQL 15 + PostGIS |
| **Cache** | Redis 7 (rate limiting Gateway + cache GPS) |
| **Messaging** | RabbitMQ 3 (TopicExchange `transport.exchange`) |
| **Sécurité** | JWT HMAC-SHA256 (JJWT 0.12.3), Spring Security 6 |
| **Notifications** | Firebase Admin SDK 9.2.0 (FCM HTTP v1, mode dégradé) |
| **WebSocket** | Spring WebSocket natif (pas STOMP) |
| **GPS routing** | OSRM local (données OSM Maroc) |
| **Langage Python** | Python 3.11+ (3.13 supporté avec libs à jour) |
| **Framework Python** | FastAPI 0.111 + Uvicorn |
| **ML clustering** | scikit-learn 1.5.2, numpy 2.1 |
| **HTTP async** | httpx 0.27 |
| **Messaging Python** | aio-pika 9.4 |
| **Résilience** | Tenacity 8.2.3 (retry exponentiel) |
| **Sécurité Python** | PyJWT 2.8 + cryptography 42 |
| **Tests** | Newman (Postman CLI) : 88/88 assertions ✅ |
| **Conteneurs** | Docker + Docker Compose |

---

## 🏗️ Architecture microservices — État S7

### ms-common (module partagé, PAS de Spring)
- `Role.java` → enum : `ADMIN`, `CHAUFFEUR`, `PARENT`
- `JwtUtils.java` → Java pur, instancié via `@Bean` dans chaque MS
  - Clé : `Base64.getEncoder().encodeToString(secret.getBytes())` + `Decoders.BASE64.decode()`
  - Méthodes : `isTokenValid()`, `extractEmail()`, `extractRole()`, `extractUserId()`
- `UserPrincipal.java` → `email`, `role`, `userId`

**Règle critique :** JwtUtils jamais `@Component`, toujours `@Bean` :
```java
@Bean public JwtUtils jwtUtils() { return new JwtUtils(jwtSecret); }
```

---

### MS7 — AuthService (port 8087) ✅ mis à jour (gestion utilisateurs)
- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/validate`
- **Gestion des utilisateurs (ADMIN)** ← NOUVEAU : `GET /api/auth/users?role=` (liste, **sans `motDePasse`**),
  `POST /api/auth/users` (créer, ne renvoie **pas** de token, ≠ register), `PUT /api/auth/users/{id}`
  (modifier ; `motDePasse` vide = inchangé), `DELETE /api/auth/users/{id}` (**refuse l'auto-suppression**, 409).
  DTO `UserResponse` (jamais de mot de passe) + `UserUpsertRequest`. Sécurité : `SecurityConfig` matcher
  `/api/auth/users/**` → `hasRole('ADMIN')` (MS7 valide déjà le JWT via `JwtAuthFilter`, autorités `ROLE_*`).
- Réponse login : `{ token, userId, nom, email, role }`
- Token JWT contient : `sub` (email), `role`, `userId`, `nom`, `iat`, `exp` (24h)
- CORS supprimé (géré uniquement MS8)

---

### MS1 — BusService (port 8081) ✅
- Entité `Bus` : `id`, `matricule` (unique), `capacite`, `statut`, `chauffeurId`, `latitude`, `longitude`
- `StatutBus` : `ACTIF`, `INACTIF`, `EN_PANNE`
- Endpoints CRUD complets + `PATCH /statut` + `PATCH /position`
- **`GET /api/bus/actifs`** (permitAll, interne) → flotte ACTIF pour la **liaison groupe↔bus** (MS6) ← NOUVEAU B1
- **RabbitMQ publie :** `bus.created`, `bus.deleted` → **déclenche le recalcul clustering MS6** (changement de flotte = changement de capacité totale → `k` peut changer). Config : `spring-boot-starter-amqp` + `RabbitMQConfig` (exchange `transport.exchange`).
- **Entité `Trajet`** : `busId`, `chauffeurId`, `groupeId`, `geometrie` (JSON `[[lat,lng],…]`), `sens`, `statut`,
  `heureDebut/Fin` + **`distancePlanM` / `dureePlanMin`** (totaux OSRM de la tournée, figés au démarrage) ← **19/08**
- **`GET /api/trajets/bus/{busId}/route`** (ADMIN/CHAUFFEUR/**PARENT**, 204 si aucun trajet) → `TrajetRouteResponse`
  = polyligne + totaux. **Séparé de `/actif`** : la géométrie pèse des dizaines de Ko et `/actif` est sondé toutes
  les 15 s par chaque front ; ici on ne recharge qu'au changement de trajet. Sert à mesurer la **distance restante
  le long du circuit** (ETA qui décroît) ← **NOUVEAU 19/08**

---

### MS2 — EleveService (port 8082) ✅ mis à jour S7

**Entité `Eleve` :**
```java
private Long id;
private String nom, prenom;
private Double latitude, longitude;
private Long parentId;   // FK logique vers MS7 (pas de contrainte SQL)
private Long busId;      // FK logique vers MS1 — assigné par ADMIN ou clustering
private Long groupeId;   // Résultat clustering MS6 (K-Means / DBSCAN)
private Boolean statutPresence;
private Integer ordrePassage;  // Rang dans la tournée (persisté par MS5-VRP ; null si non planifié) ← NOUVEAU G2
```

**Endpoints complets :**
| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| POST | `/api/eleves` | ADMIN | Créer |
| GET | `/api/eleves` | JWT | Lister tous |
| GET | `/api/eleves/{id}` | JWT | Par ID |
| GET | `/api/eleves/parent/{parentId}` | JWT | Par parent |
| GET | `/api/eleves/groupe/{groupeId}` | JWT | Par groupe |
| GET | `/api/eleves/sans-groupe` | **permitAll** | Sans groupe (MS6) |
| GET | `/api/eleves/bus/{busId}/parents` | **permitAll** | ParentIds par bus (MS4) |
| PUT | `/api/eleves/{id}` | ADMIN | Modifier complet |
| PATCH | `/api/eleves/{id}/bus?busId=X` | ADMIN | Assigner bus |
| PATCH | `/api/eleves/{id}/groupe?groupeId=X` | **permitAll** | Assigner groupe (MS6) |
| PUT | `/api/eleves/groupes/bulk` | **permitAll** | Bulk update groupeId (MS6) ← NOUVEAU |
| PUT | `/api/eleves/bus/bulk` | **permitAll** | Bulk update busId — **liaison groupe↔bus (MS6)** ← NOUVEAU B1 |
| PUT | `/api/eleves/ordre/bulk` | **permitAll** | Bulk update ordrePassage — **tournées persistées (MS5)** ← NOUVEAU G2 |
| GET | `/api/eleves/bus/{busId}` | ADMIN/CHAUFFEUR | Élèves du bus **dans l'ordre de passage** (vue chauffeur) ← NOUVEAU G2 |
| PATCH | `/api/eleves/{id}/presence` | ADMIN/CHAUFFEUR | Présence |
| DELETE | `/api/eleves/{id}` | ADMIN | Supprimer |

**SecurityConfig — routes internes sans JWT :**
```java
.requestMatchers(HttpMethod.GET,  "/api/eleves/bus/*/parents").permitAll()
.requestMatchers(HttpMethod.GET,  "/api/eleves/sans-groupe").permitAll()
.requestMatchers(HttpMethod.PATCH,"/api/eleves/*/groupe").permitAll()
.requestMatchers(HttpMethod.PUT,  "/api/eleves/groupes/bulk").permitAll()
.requestMatchers(HttpMethod.PUT,  "/api/eleves/bus/bulk").permitAll()   // liaison groupe↔bus (B1)
```

**RabbitMQ publie :** `eleve.created`, `eleve.gps.updated`, `eleve.deleted`

**Repository :**
```java
List<Eleve> findByParentId(Long parentId);
List<Eleve> findByBusId(Long busId);
List<Eleve> findByGroupeId(Long groupeId);
List<Eleve> findByGroupeIdIsNull();
```

---

### MS3 — LocalisationService (port 8083) ✅ (fix WebSocket concurrent)
- WebSocket : `ws://localhost:8083/ws/gps`
- Abonnement : `{"subscribe": "ALL"}` ou `{"subscribe": "BUS:5"}`
- Cache Redis : clé `gps:BUS:5` (TTL 2h)
- RabbitMQ publie : `gps.bus.updated`, `gps.eleve.updated`
- OSRM routing intégré
- **FIX critique ← NOUVEAU** : `GpsWebSocketHandler` enveloppe chaque session dans un
  **`ConcurrentWebSocketSessionDecorator`**. `sendMessage()` n'est **pas** thread-safe ; avec plusieurs bus
  publiant en même temps, les écritures concurrentes déclenchaient `TEXT_PARTIAL_WRITING` → la session était
  supprimée → la carte ne bougeait **qu'au refresh**. Corrigé (envois sérialisés par session, buffer 512 Ko, DROP).

---

### MS4 — NotificationService (port 8084) ✅ mis à jour S7

**Entité `Notification` (inner enums) :**
```java
public enum TypeNotification {
    INCIDENT_SIGNALE, INCIDENT_RESOLU, BUS_ARRIVE_ECOLE, BUS_EN_ROUTE, RETARD, ENFANT_A_BORD,
    ALERTE_QUALITE, ANOMALIE_DETECTEE   // ← canal admin (D1) : qualité clustering (MS6) + anomalie GPS (MS11)
}
public enum StatutEnvoi { EN_ATTENTE, ENVOYE, ECHEC }
```

**Champs :** `id`, `type`, `statutEnvoi`, `parentId`, `fcmToken`, `titre`, `message`, `sourceId`, `sourceType`, `dateEnvoi`, `erreurFcm`

**Entité `DeviceToken` :** `parentId`, `fcmToken`, `plateforme` (défaut "ANDROID"), `dateEnregistrement`, `actif`

**Endpoints :**
| Route | Auth | Description |
|-------|------|-------------|
| `POST /api/notifications/device-token` | **PARENT/CHAUFFEUR** | Enregistrer token FCM — **idempotent** : réaffecte la ligne si le token existe (un token est stable par installation) ← **25/08** |
| `DELETE /api/notifications/device-token/{token}` | **PARENT/CHAUFFEUR** | Désactiver token (au logout, **avant** d'effacer le JWT) ← **25/08** |
| `GET /api/notifications/mes-notifications` | PARENT/CHAUFFEUR | Historique personnel (ne filtre **pas** sur `statutEnvoi` : un `ECHEC` de push reste lisible en app) |
| `GET /api/notifications?page=&size=&tri=&sens=&adminSeulement=` | ADMIN | Journal **paginé côté serveur** (tri en liste blanche, page ≤ 500) ← **25/08** |
| `GET /api/notifications/stats` | ADMIN | Stats globales |

**Repository — méthode clé bugfix :**
```java
long countByStatutEnvoi(Notification.StatutEnvoi statut);  // bugfix echecs=0
```

**NotificationService — méthodes :**
- `enregistrerToken(Long parentId, DeviceTokenRequest req)`
- `supprimerToken(String fcmToken)`
- `getMesNotifications(Long parentId)` → `List<NotificationResponse>`
- `getToutesNotifications()` → `List<NotificationResponse>`
- `getStats()` → `Map<String, Long>` (total, envoyes, echecs, attente, **alertesAdmin** — compté en base depuis que la console ne reçoit plus qu'une page) ← **25/08**
- `envoyerAuParent(Long, TypeNotification, String, String, Long, String)`

**FcmService.envoyerAuParent signature exacte :**
```java
public void envoyerAuParent(Long parentId, TypeNotification type,
                             String titre, String message,
                             Long sourceId, String sourceType)
```

**RabbitMQ consumers :**
- `ms4.incident.signale.queue` → `incident.signale`
- `ms4.incident.resolu.queue` → `incident.resolu`
- `ms4.gps.bus.updated.queue` → `gps.bus.updated` (arrivée école à ≤150 m → `BUS_ARRIVE_ECOLE`)
- `ms4.eta.arriving.queue` → `eta.bus.arriving` (MS12) → « le bus arrive dans ~10 min » (`BUS_EN_ROUTE`, UC-4) ← **NOUVEAU G1**
- `ms4.eleve.presence.queue` → `eleve.presence.updated` (MS2) → « enfant à bord » (`ENFANT_A_BORD`, UC-4) au parent précis ← **NOUVEAU G5**
- `ms4.quality.queue` → `clustering.quality.low` (MS6) → alerte admin `ALERTE_QUALITE` (canal admin D1) ← **NOUVEAU**
- `ms4.anomalie.queue` → `anomalie.detectee` (MS11) → alerte admin `ANOMALIE_DETECTEE` (canal admin D1) ← **NOUVEAU**

**Statut FCM :** mode dégradé (placeholder JSON) — ECHEC en DB, fonctionnel dès vrai `firebase-service-account.json`

**Test validé :** flow MS10→RabbitMQ→MS4 ✅ — 6 notifications en DB, stats `echecs: 6` correct (bugfix validé)

---

### MS6 — ClusteringService (port 8086) ✅ refonte data-science « expert » v3

**Technologie :** Python 3.11+ / FastAPI. Pipeline reproductible, géographiquement correct et
**conscient de la capacité des bus** (≠ simple appel sklearn).

**Modèle de PRODUCTION final :** **k-médoïdes capacitaire sur distance routière OSRM** (repli euclidien).
Pipeline en 3 étapes dans `clustering.py::production_clustering` :
1. **Dispersés** — DBSCAN sur la matrice de distances détecte les élèves isolés (signalés pour ramassage individuel).
2. **Nombre de bus** — courbe de **Pareto** (qualité vs nb de bus) sur le cœur ; `k_min = ⌈N/capacité⌉`.
3. **Affectation globale capacitaire** — problème de transport (LP / min-cost-flow, `scipy.optimize.linprog`)
   de TOUS les élèves aux médoïdes → **taille ≤ capacité garantie par construction**. Les dispersés sont
   affectés au médoïde le plus proche (pas de groupe 999 en production).

**Rigueur géographique :** projection **UTM Zone 30N (EPSG:32630, `pyproj`)** → coordonnées en **mètres**
(remplace `StandardScaler(lat,lon)` qui fausse la géométrie à 33.9°N). Silhouette/compacité interprétables en mètres.

**Capacité = paramètre métier uniforme** (tous les bus de même taille, **taille modifiable**) :
`capacity` (query param) → sinon `settings.bus_capacity` (`.env`, défaut **50**). Le nombre de bus s'adapte
automatiquement (`k = ⌈N/capacité⌉` + Pareto). *(Flotte hétérogène = évolution S8, `ms1_client.get_capacites()` prêt mais non branché.)*

**2ᵉ paramètre métier AJUSTABLE — `rayon` (S10) :** distance routière **max élève→médoïde** (m ; `0` = désactivé).
`rayon` (query param) → sinon `settings.rayon_max_m` (`.env`). Contrainte **dure** (SLA compacité) : arcs > R
interdits dans le LP ; les élèves sans bus à ≤ R deviennent **non affectés → groupe 999** (ramassage individuel) ;
repli glouton si LP infaisable. **Arbitrage mesuré** (notebook `06_rayon_max_study.ipynb`) : R↓ ⇒ compacité
garantie ↑ & silhouette cœur ↑, **au prix de** plus de bus et/ou plus de dispersés (ex. R=1500 → compacité_max≤1500, ~3 dispersés ; R=1000 → ~40 dispersés, silhouette 0.57).

**Fichiers (refonte modulaire) :**
```
ms6-clustering/
├── main.py           ← FastAPI app + JWT, endpoints production/pareto/diagnostics
├── clustering.py     ← Orchestrateur (production_clustering, pareto_flotte, diagnostics, legacy)
├── features.py       ← projection UTM 30N (pyproj), matrices haversine/euclidienne
├── algorithms.py     ← kmeans, kmedoids_capacitaire, dbscan_precomputed, affectation_capacitaire (LP)
├── evaluation.py     ← Silhouette, Davies-Bouldin, Calinski-Harabasz, KPI métier (faisabilité, compacité)
├── selection.py      ← pareto(), choisir_k() (garde-fou Silhouette ≥ 0.5)
├── osrm_client.py    ← matrice routière OSRM /table (async, blocs de 50, cache)
├── ms1_client.py     ← capacités flotte MS1 (httpx + Tenacity) — non branché en prod
├── ms2_client.py     ← httpx + Tenacity retry (bulk update)
├── rabbitmq.py       ← Consumer aio-pika + asyncio.Lock() (recalcul auto = production)
├── config.py         ← pydantic-settings
├── data/             ← eleves_meknes.csv (v2), osrm_dist_m.npy (matrice routière cachée)
├── notebooks/        ← clustering_study (CRISP-DM), 02_model_comparison (11 algos), 03_production_strategy
├── requirements.txt
└── .env
```

**requirements.txt (ajouts data-science) :**
```
fastapi==0.111, uvicorn[standard]==0.29, scikit-learn==1.5.2, numpy==2.1
pyproj (UTM), scipy (LP affectation capacitaire), k-means-constrained
httpx==0.27, aio-pika==9.4.1, pydantic-settings==2.3, tenacity==8.2.3
PyJWT==2.8, cryptography==42.0.8
# notebooks : matplotlib, seaborn, folium, jupyter
```

**Endpoints :**
| Route | Auth | Description |
|-------|------|-------------|
| GET `/api/clustering/health` | Public | Health check |
| GET `/api/clustering/eleves` | Public | Tous les élèves (MS2) |
| GET `/api/clustering/sans-groupe` | Public | Élèves sans groupeId |
| GET `/api/clustering/diagnostics` | Public | Stats EDA + `k` recommandé (⌈N/capacité⌉) |
| GET `/api/clustering/quality` | Public | **Garde-fou qualité** : baseline dynamique + seuils + dernier verdict (dashboard admin) ← **NOUVEAU** |
| POST `/api/clustering/production?appliquer=&capacity=&rayon=&road=` | **JWT ADMIN** | **Modèle final** : k-médoïdes capacitaire routier (+ contrainte `rayon` optionnelle) + bulk update MS2 (+ `quality` dans la réponse). Renvoie aussi **`assignments`** `{eleveId: groupe}` ← NOUVEAU → **carte de prévisualisation** web-admin même sans `appliquer` (DB intacte) |
| POST `/api/clustering/pareto?capacity=&road=` | **JWT ADMIN** | Courbe Pareto qualité vs nb de bus (sans écrire) |
| POST `/api/clustering/kmeans?appliquer=` | **JWT ADMIN** | *(legacy)* K-Means projeté mètres |
| POST `/api/clustering/dbscan?appliquer=` | **JWT ADMIN** | *(legacy)* DBSCAN projeté mètres, bruit → 999 |
| POST `/api/clustering/comparer` | **JWT ADMIN** | *(legacy)* K-Means vs DBSCAN |

**Config de production gelée (`notebooks/production_config.json`, capacité 50) :**
`k=7 bus · Silhouette routier 0.43 · compacité médiane 725 m / max 2409 m · taille_max 50 · faisable ✅ · 17 dispersés`
> Silhouette 0.43 < seuil 0.5 = **arbitrage assumé** capacité ↔ compacité (sans contrainte KMeans monte plus haut mais produit des groupes infaisables).

**Garde-fou qualité DYNAMIQUE (`quality.py`) :** à chaque recalcul, produit un **verdict** `OK / DEGRADE / CRITIQUE`
(informatif, pas un déclencheur). **PAS un seuil fixe 0.5** (qui serait toujours rouge puisque notre silhouette est 0.43) :
- **CRITIQUE** si capacité dépassée (`taille_max > capacité`, contrainte dure) **ou** silhouette < **plancher** (0.75 × 0.4334 ≈ **0.325**, ancré sur le point de conception) ;
- **DEGRADE** si **régression relative** vs référence : silhouette −15 % (et −0.05 abs), ou compacité max +25 %, ou dispersés +15 ;
- **référence dynamique** = `data/quality_baseline.json`, **bootstrap depuis `production_config.json` (0.43, jamais 0.5)**, réécrite à chaque run **OK appliqué** (roulante).
Exposé via `GET /api/clustering/quality` + champ `quality` de `/production` + logs WARNING. Seuils ajustables (`.env` `QUALITY_*`).

**Pattern Bulk Update (anti-DDoS interne) :** une seule requête `PUT /api/eleves/groupes/bulk` au lieu de 300 PATCH.

**Liaison groupe↔bus (B1, `binding.py`) :** à l'**application** du clustering (endpoint `/production?appliquer=true`
et recalcul auto RabbitMQ), MS6 résout chaque groupe (1..k) vers un **bus MS1 actif** (`GET /api/bus/actifs`,
mapping 1-1 par id — capacité uniforme) puis **propage `busId`** aux élèves (`PUT /api/eleves/bus/bulk`).
**Indispensable** : sans ça, `findByBusId` (MS4/ETA) renvoie vide → aucun parent notifié. Dispersés (999) → pas de bus ;
flotte insuffisante / MS1 indispo → dégradé (partiel + WARNING). Rapport `bus_binding` dans la réponse `/production`.

**Consumer RabbitMQ :** queue `ms6.clustering.queue`, keys `eleve.created/gps.updated/deleted` (MS2) + `bus.created/bus.deleted` (MS1, déclencheur « nouveau bus »), `asyncio.Lock()`.
Le recalcul auto utilise désormais `production_clustering` (chemin capacitaire).

**Sécurité JWT :** routes POST protégées par `verify_token` (ADMIN), `jwt_secret` = même valeur que MS7.
**CORS :** aucun (géré uniquement par la Gateway — `CORSMiddleware` retiré).

**Variables .env MS6 :**
```env
MS2_URL=http://localhost:8082
MS1_URL=http://localhost:8081
OSRM_URL=http://localhost:5000
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
JWT_SECRET=<même valeur que MS7 application.properties>
BUS_CAPACITY=50            # capacité uniforme paramétrable
RAYON_MAX_M=0              # distance max élève→médoïde (m) ; 0 = désactivé (ajustable comme la capacité)
USE_ROAD_DISTANCE=true     # distance routière OSRM (false = euclidienne projetée)
EPSG_METRIC=32630          # UTM 30N
MIN_SILHOUETTE=0.50
```

**Démarrage :**
```bash
cd ms6-clustering
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8086 --reload
```

---

### MS8 — API Gateway (port 8080) ✅ mis à jour S7

- JwtAuthFilter → bypass OPTIONS, injecte `X-User-Email`, `X-User-Role`, `X-User-Id`
- Rate limiting Redis : 20 req/s global, 5 req/s sur `/auth`
- CORS global dans `application.yml`
- **Route MS6 à ajouter dans application.yml :**
```yaml
- id: ms6-clustering
  uri: http://localhost:8086
  predicates:
    - Path=/api/clustering/**
  filters:
    - name: RequestRateLimiter
      args:
        redis-rate-limiter.replenishRate: 5
        redis-rate-limiter.burstCapacity: 10
```

---

### MS10 — IncidentService (port 8090) ✅
- `StatutIncident` : `SIGNALE` → `CONFIRME` → `EN_TRAITEMENT` → `RESOLU`
- `TypeIncident` : `ACCIDENT`, `PANNE`, `RETARD`, `ABSENCE_CHAUFFEUR`, `ROUTE_BLOQUEE`, `AUTRE`
- RabbitMQ publie : `incident.signale`, `incident.resolu`
- PATCH `/api/incidents/{id}/statut` → déclenche publication si RESOLU

---

### MS12 — PredictionService ETA (port 8088) ✅ NOUVEAU S8

**Technologie :** Python 3.11 / FastAPI. Prédiction du **temps d'arrivée (ETA)** d'un tronçon de trajet bus.
Démarche data-science identique à MS6 : **benchmark multi-modèles** → choix du meilleur → gel de l'artefact.

**Modèle de production :** choisi par benchmark honnête (**elasticnet** gagnant sur le run actuel).
Le service charge l'artefact gelé de façon **agnostique** (n'importe quel régresseur sklearn/xgboost/lightgbm).

**Stratégie de données (B) — semi-réel ancré OSRM :** durée de base de chaque tronçon = **vraie route OSRM
de Meknès** ; facteurs trafic/météo/Ramadan/souk/travaux issus de la littérature transport ; **incidents**
(panne, accident, route bloquée, absence chauffeur, retard admin) en queue lourde (~5 %/trajet).
`incident_type` = **label** (imprévisible → pas une feature) réutilisable en S12 (anomalies).

**Résultats gelés (`data/eta_config.json`, run OSRM réel) :**
`gagnant elasticnet · R² normaux 0.82 · MAE normaux 0.86 min · gain +52.7 % vs baseline OSRM ·
R² tous 0.16 (incidents irréductibles, assumé)`.

**Fichiers :**
```
ms12-prediction/
├── main.py           ← FastAPI + JWT (ADMIN/CHAUFFEUR) : health / model-info / predict
├── config.py         ← pydantic-settings (port 8088, jwt_secret, osrm_url, chemins artefacts)
├── features.py       ← feature engineering (heure cyclique, one-hot météo/trafic, binaires) — partagé
├── dataset.py        ← générateur ~180 jours d'école, ancré OSRM, facteurs + incidents (seed=42)
├── osrm_client.py    ← durée/distance point-à-point (async service + sync dataset, repli haversine)
├── algorithms.py     ← catalogue des régresseurs candidats (baselines→linéaires→forêts→boosting)
├── train.py          ← split TEMPOREL → benchmark → choix gagnant → gel (model/config/benchmark)
├── model.py          ← chargement/prédiction agnostique du gagnant
├── data/             ← eta_dataset.csv, eta_model.pkl, eta_config.json, benchmark_summary.json
├── notebooks/        ← 01_eta_data_study, 02_model_comparison, 03_production_strategy (+ figures/)
├── requirements.txt  ← Python 3.11 : numpy 1.26.4, pandas, scikit-learn 1.5.2, xgboost 2.1.1, lightgbm 4.5.0
├── Dockerfile        ← EXPOSE 8088
└── .env
```

**Endpoints :**
| Route | Auth | Description |
|-------|------|-------------|
| GET `/api/eta/health` | Public | Health + modèle chargé |
| GET `/api/eta/model-info` | Public | Métriques (tous/normaux), gain vs baseline, importances |
| POST `/api/eta/predict` | **JWT ADMIN/CHAUFFEUR/PARENT** | ETA d'un trajet (coords→OSRM ou distance/durée fournies). Hors du domaine d'entraînement → bascule **facteur de contexte** (champ `mode_eta`) ← **19/08** |

**Features (dispo à l'heure de départ) :** temporel (heure sin/cos, jour, mois, moment), conditions
(météo, trafic), route (distance/durée OSRM, nb_feux, traverse_oued), dwell (montées/descentes,
taux_occupation), contexte marocain (ramadan, jour_souk), travaux planifiés, **historique/lag**
(duree_moyenne_historique sans fuite, retard_cumule).

**Protocole d'évaluation :** split **temporel** (30 derniers jours = test), métriques MAE/RMSE/R²/MAPE,
**double vue** (tous trajets vs trajets normaux), baseline métier = durée OSRM brute.

**Pipeline ETA temps réel (G1) — `rabbitmq.py` :** MS12 consomme `gps.bus.updated` (MS3), calcule l'ETA
bus→école (modèle + OSRM), et publie `eta.bus.arriving` dès que l'ETA ≤ `ETA_ALERT_MIN` (10 min) →
MS4 pousse la notif parents (**UC-4**). Réutilise l'endpoint `predict()` (import différé, `auto_context=True`).
Garde-fous : throttle 20 s + cooldown 30 min par bus. `.env` : `RABBITMQ_URL`, `EXCHANGE_NAME`, `ETA_ALERT_MIN`,
`ECOLE_LAT/LNG`. Consumer démarré dans le `lifespan` (mode dégradé si RabbitMQ absent).

**Sécurité JWT :** `verify_token` (même `jwt_secret` que MS7). **CORS :** aucun (géré par la Gateway).

**Démarrage :**
```bash
cd ms12-prediction
pip install -r requirements.txt      # env conda "nlp" (Python 3.11)
python dataset.py                    # génère data/eta_dataset.csv (OSRM requis, sinon repli)
python train.py                      # benchmark + gel du meilleur modèle
uvicorn main:app --host 0.0.0.0 --port 8088
```

> **MS9 ≠ MS12 :** MS9 (port 8089) est réservé au **chatbot LLM** (S9) ; la prédiction ETA est **MS12** (8088).

---

### MS11 — AnalytiqueService / Détection d'anomalies (port 8091) ✅ NOUVEAU (S12 anticipé)

**Technologie :** Python 3.11 / FastAPI. **Détection d'anomalies non supervisée** (Isolation Forest) sur les
trajets de bus, **évaluée** contre le label `incident_type` généré par MS12 (labels = évaluation seulement).
Route Gateway `ms11-analytique` (8091, `/api/analytique/**`) **déjà présente**.

**Données :** **dataset PROPRE à MS11** (`data/anomaly_dataset.csv`, généré par `dataset_anomaly.py`,
indépendant de MS12) avec **anomalies hétérogènes et contextuelles** (~1,25 %) : *franc* (panne/accident,
ratio énorme), *contextuel* (ratio modéré mais conditions légères), *surcharge* (montées anormales).
**Signaux** : `ratio` (franc), **`surprise` = ratio ajusté au contexte** (contextuel), `dwell`/`nb_montees` (surcharge).

**Benchmark de 4 détecteurs (split temporel, budget d'alerte fixe) — résultat gelé :**
| Détecteur | PR-AUC | ROC-AUC | F1 | P | R |
|---|---|---|---|---|---|
| **iforest_curated 🏆** | **0.91** | **1.00** | **0.78** | 0.70 | **0.88** |
| seuil_surprise | 0.80 | 0.99 | 0.63 | 0.55 | 0.75 |
| seuil_ratio | 0.79 | 0.94 | 0.67 | 0.60 | 0.75 |
| iforest_all (dilué) | 0.48 | 0.98 | 0.44 | 0.40 | 0.50 |

> **Triple leçon DS (honnête) :** (1) le **feature engineering** prime (`surprise` contextuelle > ratio brut) ;
> (2) la **curation** prime (`iforest_curated` ≫ `iforest_all` dilué) ; (3) le **multivarié gagne** car les
> anomalies sont hétérogènes (franc+contextuel+surcharge) — aucun seuil univarié ne les capte toutes.
> Contraste avec MS12 (modèle simple gagnant) : ici le problème est **réellement multivarié**. **Scan full : précision 0.70 · rappel 0.72.**

**Fichiers :** `main.py`, `config.py`, `dataset_anomaly.py` (dataset propre), `features.py` (ratio + **surprise**
contextuelle + dwell), `anomaly.py` (seuil | IsolationForest curé, joblib), `train_anomaly.py` (benchmark 4
détecteurs + gel), `osrm_client.py`, `data/` (anomaly_dataset.csv, anomaly_model.pkl, anomaly_config.json,
anomaly_benchmark.json), `notebooks/04_anomaly_detection.ipynb`, Dockerfile, `.env`.

**Endpoints :**
| Route | Auth | Description |
|-------|------|-------------|
| GET `/api/analytique/health` | Public | Health + détecteur chargé |
| GET `/api/analytique/model-info` | Public | Métriques (PR-AUC/ROC/F1), seuil, contamination |
| POST `/api/analytique/anomalies` | **JWT ADMIN** | Un trajet observé (durée réelle + base/coords + contexte) → `{is_anomaly, anomaly_score, ratio, niveau}` |
| GET `/api/analytique/anomalies/scan?limit=` | **JWT ADMIN** | Scanne le dataset → top anomalies + précision/rappel vs incidents réels |
| GET `/api/analytique/live?limit=` | Public | **Monitor GPS live (G3)** : anomalies instantanées détectées en temps réel ← **NOUVEAU** |

**Monitor GPS live (G3, `live_monitor.py` + `rabbitmq.py`) :** MS11 consomme `gps.bus.updated` (queue `ms11.gps.queue`)
et applique des **règles instantanées** (UC-8) : **arrêt prolongé** (immobile > `SEUIL_ARRET_MIN`) et **vitesse anormale**
(> `SEUIL_VITESSE_KMH`). Complément du **détecteur ML** (Isolation Forest, post-hoc au niveau trajet) : le modèle
score des *trajets complets*, inadapté à un ping GPS. Sortie = **buffer mémoire + logs**, exposée par `GET /api/analytique/live`
(pas d'événement sans consommateur ; évolution : `anomalie.detectee` → MS10/MS4 quand un canal admin existera).
La **déviation** (3ᵉ signal UC-8) nécessite la route planifiée persistée (G2).

**Sécurité JWT :** `verify_token` ADMIN (même `jwt_secret` que MS7). **CORS :** aucun (Gateway).
**Démarrage :** `cd ms11-analytique && python train_anomaly.py && uvicorn main:app --port 8091` (env `nlp`).

---

### MS5 — PlanificationService / VRP (port 8085) ✅ NOUVEAU (S10)

**Technologie :** Python 3.11 / FastAPI + **OR-Tools**. **Optimisation des tournées** : le clustering MS6 affecte
les élèves aux bus (capacité) ; MS5 calcule **l'ordre de passage optimal** de chaque bus.

**Modèle :** un **TSP par groupe/bus**, **dépôt = école** (part de l'école → ramasse → revient), coût d'arc =
**durée routière OSRM réelle**. Résolu par **OR-Tools** (`PATH_CHEAPEST_ARC` + `GUIDED_LOCAL_SEARCH`).
Baseline « plus proche voisin » pour mesurer le **gain**. `sens=soir` → dépose sur la **même** tournée
(**même ordre** que le matin, PAS l'inverse) : garder le même ordre équilibre le **temps à bord** sur la journée
(écart-type ≈ 0 vs ~5.8 min si inversé) et, sur OSRM réel (asymétrique), l'inversé non ré-optimisé coûte ~2× plus.
Preuve : `ms5-planification/verify_sens.py`.

**Résultat mesuré (7 bus, partition de production, rejoué le 29/08) :** durée totale de flotte **206,6 min**
(contre 241,5 min en ordre naïf) · **gain moyen 13,3 %** (3,9 % à 23,2 % selon la géométrie du groupe)
*(l'ancien « 9 bus · ~108 km · ~224 min · ~12,6 % » datait des données v2, avant la migration k=7 du 27/08)*
vs l'ordre naïf (variable par bus : 0 % si le glouton est déjà optimal).

**Perf `/tournees` ← NOUVEAU :** calcul **parallèle** des tournées (`asyncio.gather`) + solve OR-Tools exécuté
dans un **thread** (`asyncio.to_thread`, le GIL est libéré) → **~43 s → ~9 s** pour toute la flotte (le goulot
était le time-limit OR-Tools bloquant l'event loop en série). *(Côté web-admin, ces appels lourds ont un timeout
axios dédié de 120 s + feedback.)*

**Fichiers :** `main.py`, `config.py`, `ms2_client.py` (élèves par groupe, **filtré depuis `/api/eleves`** —
MS5 n'a pas de token utilisateur), `osrm_client.py` (matrice `/table` + géométrie `/route` GeoJSON),
`vrp.py` (OR-Tools TSP + baseline), `planner.py` (orchestrateur), `notebooks/05_vrp_study.ipynb`, Dockerfile, `.env`.

**Endpoints :**
| Route | Auth | Description |
|-------|------|-------------|
| GET `/api/planification/health` | Public | Health + solveur |
| POST `/api/planification/tournee?groupeId=&sens=matin\|soir` | **JWT ADMIN/CHAUFFEUR** | Tournée d'un bus → `{ordre, distance_m, duree_min, gain_vs_baseline_%, geometrie}` |
| POST `/api/planification/tournees?sens=` | **JWT ADMIN/CHAUFFEUR** | Toutes les tournées (lit l'affectation MS6 via MS2) + totaux + gain moyen |
| POST `/api/planification/mes-enfants?sens=` | **JWT PARENT** | **Étapes des SEULS enfants du parent** (rang + cumul distance/durée depuis l'école) — portée prise dans le JWT, jamais dans la requête ← **NOUVEAU 19/08** |

> **Pourquoi un endpoint dédié au parent** : `/tournee` expose l'ordre **et les domiciles de toutes les familles**
> du bus. L'ouvrir au rôle PARENT serait une fuite. MS5 calcule donc la tournée complète (indispensable au cumul)
> puis **filtre sur `parentId` du jeton** avant de répondre.

**Sécurité JWT :** `verify_token` ADMIN/CHAUFFEUR (même `jwt_secret` que MS7). **CORS :** aucun (Gateway).
**Gateway :** route `ms5-planification` (8085) **déjà présente** → aucune modif.
**Démarrage :** `cd ms5-planification && uvicorn main:app --port 8085` (env `nlp` + `pip install ortools`).
> **Complémentarité :** MS6 = *quel bus* (affectation capacitaire) ; MS5 = *quel ordre* (temps de tournée).

**Benchmark CVRP global ✅ (23/08)** — `cvrp.py` + `notebooks/06_cvrp_benchmark.ipynb`. Protocole : une seule
matrice OSRM (assemblée **par blocs de 50×50**, `/table` plafonnant à 100 coordonnées), même grandeur
minimisée, même arrondi, **budget égalisé** (A = k TSP × 5 s ; B = 1 résolution de k × 5 s), même flotte.
Sur les **300 élèves / 7 groupes réels** : le CVRP **ne bat jamais** la décomposition de plus de 0,2 % et lui
est le plus souvent inférieur (jusqu'à −2,3 %). Explication : les k-médoïdes de MS6 travaillent **déjà sur la
distance routière**, donc l'information géographique est injectée *avant* le routage — la décomposition est
une **façon d'injecter de la connaissance du domaine**, pas une approximation subie.
**Mais** le CVRP n'utilise que **6 bus sur 7** (chargés à 50/50, écart-type 0,00 vs 7,49) : un bus et un
chauffeur économisés pour +0,4 % de conduite. Arbitrage, pas erreur — le 7ᵉ bus de MS6 achète de la compacité
**et de la marge** (à 6 bus pleins, un élève de plus rend l'instance infaisable).
**Verdict : on garde MS6+TSP**, et le CVRP devient un outil de **dimensionnement de flotte**.

---

## 🔁 RabbitMQ — Exchange et queues

**Exchange :** `transport.exchange` (TopicExchange, durable)

| Routing Key | Publisher | Consumer | Queue |
|-------------|-----------|----------|-------|
| `eleve.created` | MS2 | MS6 | `ms6.clustering.queue` |
| `eleve.gps.updated` | MS2 | MS6 | `ms6.clustering.queue` |
| `eleve.deleted` | MS2 | MS6 | `ms6.clustering.queue` |
| `bus.created` | **MS1** | MS6 | `ms6.clustering.queue` ← **NOUVEAU (déclencheur « nouveau bus »)** |
| `bus.deleted` | **MS1** | MS6 | `ms6.clustering.queue` ← **NOUVEAU** |
| `gps.bus.updated` | MS3 | MS4 | `ms4.gps.bus.updated.queue` |
| `gps.bus.updated` | MS3 | **MS12** | `ms12.eta.queue` ← **NOUVEAU (pipeline ETA temps réel G1)** |
| `gps.bus.updated` | MS3 | **MS11** | `ms11.gps.queue` ← **NOUVEAU (monitor anomalies GPS live G3)** |
| `eta.bus.arriving` | **MS12** | MS4 | `ms4.eta.arriving.queue` ← **NOUVEAU** |
| `eleve.presence.updated` | **MS2** | MS4 | `ms4.eleve.presence.queue` ← **NOUVEAU (G5 « enfant à bord »)** |
| `clustering.quality.low` | **MS6** | MS4 | `ms4.quality.queue` ← **NOUVEAU (canal admin D1 — alerte qualité)** |
| `anomalie.detectee` | **MS11** | MS4 | `ms4.anomalie.queue` ← **NOUVEAU (canal admin D1 — anomalie GPS + déviation)** |
| `incident.signale` | MS10 | MS4 | `ms4.incident.signale.queue` |
| `incident.resolu` | MS10 | MS4 | `ms4.incident.resolu.queue` |
| `trajet.demarre` | **MS1** | MS4 | `ms4.trajet.queue` ← **NOUVEAU (alerte admin trajet démarré)** |
| `trajet.termine` | **MS1** | MS4 | `ms4.trajet.queue` ← **NOUVEAU (alerte admin trajet terminé)** |
| `trajet.demarre` | **MS1** | **MS11** | `ms11.trajet.queue` ← **NOUVEAU (fige la route → surveillance déviation UC-8)** |
| `trajet.termine` | **MS1** | **MS11** | `ms11.trajet.queue` ← **NOUVEAU (purge la route de référence)** |
| `parametres.updated` | **MS13** | MS4 | `ms4.parametres.queue` (durable) ← **NOUVEAU** |
| `parametres.updated` | **MS13** | MS5·MS6·MS9·MS11·MS12 | file **exclusive par service** (cf. piège n° 22) ← **NOUVEAU** |

> **Pipeline ETA temps réel (G1) :** `MS3 gps.bus.updated → MS12` calcule l'ETA bus→école (modèle + OSRM),
> et dès que l'ETA ≤ `ETA_ALERT_MIN` (10 min) publie `eta.bus.arriving → MS4` qui pousse la notification
> aux parents (UC-4). Garde-fous : throttle (recalcul ≤ 1×/20 s par bus) + cooldown (alerte ≤ 1×/30 min par bus).
> Limite assumée : alerte à l'arrivée **école** (destination unique) ; l'ETA par arrêt élève nécessite la tournée
> persistée (G2/MS5) + le suivi de présence (G5).

---

## 🔐 Sécurité — Pattern commun MS Java

```java
// 1. JwtUtilsConfig.java
@Bean public JwtUtils jwtUtils() { return new JwtUtils(jwtSecret); }

// 2. JwtAuthFilter.java extends OncePerRequestFilter
// → extrait Bearer → valide → set UserPrincipal dans SecurityContext
// → attribute "jwt_error" si token invalide (distingue 401 manquant vs invalide)

// 3. SecurityConfig.java
@EnableWebSecurity @EnableMethodSecurity
// authenticationEntryPoint → "Token manquant" vs "Token invalide"
// CORS supprimé de chaque MS (géré uniquement Gateway)
```

**RBAC :** `@PreAuthorize("hasRole('ADMIN')")` / `@PreAuthorize("hasAnyRole('ADMIN','CHAUFFEUR')")`

---

## 🧪 Tests & Interfaces HTML

| Fichier | Service(s) | Statut |
|---------|-----------|--------|
| **`html_tests/simulation-control.html`** | **TOUS rôles** — panneau de simulation e2e : choisir chauffeur/parent, démarrer trajet, animer le GPS, présence, anomalies, **déviation**, incident+résolution, diffusion, message ; observer dans les pages React | ✅ **tests finaux** |
| **`html_tests/test-console.html`** | **TOUS** (Auth/Bus/Élèves/GPS/Clustering/Incidents/Notif) — console unifiée + cartes Leaflet (nuages de clusters + bus temps réel) | ✅ **principal** |
| `html_tests/test-gps.html` | MS3 WebSocket GPS | ✅ |
| `html_tests/map-gps.html` | MS3 + OSRM Leaflet | ✅ |
| `html_tests/test-incidents-notifications.html` | MS10 + MS4 | ✅ validé S7 |
| `html_tests/test_ms6.html` | MS6 clustering | ✅ |

**Newman :** 88/88 assertions ✅
**Guide de soutenance :** `docs/DEMO_SOUTENANCE.md` (pipeline DS → démo live → Q/R jury)

---

## 📦 Ordre de démarrage

```bash
# 1. Infrastructure
docker-compose up -d
docker start osrm_meknes

# 2. Java microservices (ordre important)
cd ms7-auth      && mvn spring-boot:run   # 8087
cd ms13-parametres && mvn spring-boot:run # 8092 (tôt : les autres y lisent leur config)
cd ms1-bus       && mvn spring-boot:run   # 8081
cd ms2-eleves    && mvn spring-boot:run   # 8082
cd ms3-localisation && mvn spring-boot:run # 8083
cd ms10-incidents && mvn spring-boot:run  # 8090
cd ms4-notifications && mvn spring-boot:run # 8084
cd ms8-gateway   && mvn spring-boot:run   # 8080 (en dernier)

# 3. Python — MS6 clustering + MS12 prédiction ETA
cd ms6-clustering  && uvicorn main:app --port 8086 --reload
cd ms12-prediction && uvicorn main:app --port 8088 --reload   # env conda "nlp" (Python 3.11)
cd ms11-analytique && uvicorn main:app --port 8091 --reload   # anomalies (env "nlp")
cd ms5-planification && uvicorn main:app --port 8085 --reload  # VRP tournées (env "nlp" + ortools)
# (raccourci : start-all-ms.bat lance tout, chaque MS dans son terminal)

# 4. Console d'administration web (React + Vite, gestionnaire Bun)
cd frontend/web-admin && bun install && bun run dev   # http://localhost:5173 (admin@transport.ma / Admin123!)

# 5. App mobile PARENT (Flutter) — config par cible, aucun code à modifier
cd frontend/parent-mobile && flutter pub get
flutter run -d chrome --web-port 5174 --dart-define-from-file=config/env.chrome.json  # navigateur (localhost)
flutter run --dart-define-from-file=config/env.phone.json                              # téléphone (IP LAN)
# ⇒ si l'IP du PC change, éditer UNIQUEMENT config/env.phone.json (+ pare-feu 8080/8083)
# ⇒ ou lancer en 1 clic via VS Code : .vscode/launch.json (« Parent App — Chrome » / « — Téléphone »)

# 6. App mobile CHAUFFEUR (Flutter) — même mécanique, port web différent
cd frontend/chauffeur-mobile && flutter pub get
flutter run -d chrome --web-port 5175 --dart-define-from-file=config/env.chrome.json  # navigateur
flutter run --dart-define-from-file=config/env.phone.json                              # téléphone
# ⇒ VS Code : « Chauffeur App — Chrome » / « — Téléphone »
# ⇒ l'interrupteur « Transmettre ma position » est OFF par défaut : le laisser OFF tant que
#    bus_simulator.py tourne (deux sources GPS sur le même bus se contrediraient).
```

---

## 📋 Planning — État d'avancement

| Sprint | Dates | Statut | Contenu |
|--------|-------|--------|---------|
| S1 | 13-19/05 | ✅ | Conception, UML, GitHub |
| S2 | 20-26/05 | ✅ | Docker Compose base |
| S3 | 27/05-02/06 | ✅ | PostgreSQL+Redis+RabbitMQ, MS7-Auth |
| S4 | 03-09/06 | ✅ | MS1-Bus, MS2-Eleves, MS8-Gateway, Newman 88/88 |
| S5 | 10-16/06 | ✅ | MS3-Localisation, WebSocket GPS, Seeding 300 élèves |
| S6 | 17-23/06 | ✅ | OSRM, Simulateur bus, MS10-Incidents, MS4-Notifications FCM |
| **S7** | **24-30/06** | **✅** | **MS6 Clustering refonte expert v3 (UTM, k-médoïdes capacitaire routier OSRM, Pareto, 3 notebooks CRISP-DM), données v2, console de test unifiée + cartes, fix CORS** |
| **S8** | **01-07/07** | **✅** | **MS12 Prédiction ETA (dataset 180j ancré OSRM, benchmark → elasticnet, service :8088). Déclencheurs clustering : ajout élève / déménagement / nouveau bus (MS1→MS6) ✅ ; silhouette dégradée = garde-fou informatif (pas trigger)** |
| **S8-S12** | **08-16/07** | **✅** | **Couche d'intégration temps réel (validée e2e 8/8) : G1 ETA→notif (MS3→MS12→MS4), G3 anomalies GPS live (MS11), G5 présence→notif, B1 liaison groupe↔bus, garde-fou qualité dynamique. Données comptes générées (parents/fratries/flotte)** |
| S9 | 08-14/07 | ✅ | **MS9 chatbot LLM (Phases A et B)** — **Phase A** : agent tool-calling maison (sans LangChain), agnostique Groq/Gemini, FR/AR/darija, outils scopés parent, reverse geocoding OSM. **Phase B ✅** : NL2SQL admin (`/api/llm/admin/query`, rôle Postgres `ms9_readonly` + transaction READ ONLY, page `AdminAssistant.tsx`) |
| S10 | 15-21/07 | ✅ | **VRP OR-Tools ✅ (MS5 : TSP par bus, dépôt=école, gain **13,3 %** sur la partition k=7, soir=même ordre que matin, service :8085 ; `/tournees` parallélisé ~9 s)** |
| **S11** | **22-28/07** | **✅** | **Console d'administration web (UC-13) — React 18 + Vite + TS + Bun + Tailwind v4 (`frontend/web-admin/`, :5173) : dashboard+graphiques, carte live (bus interpolés/ETA/anomalies/tournées), clustering (cartes clusters DB + prévisualisation), CRUD élèves/bus/utilisateurs + liaisons parent↔enfant & chauffeur↔bus, incidents, anomalies, prévisions ETA par arrêt, pagination/tri/CSV, ⌘K, nav mobile. Deltas back : MS7 users CRUD, MS3 fix WS, MS6 `assignments`** |
| S12 | 29/07-04/08 | ✅ | **Anomalies ✅ (MS11 : Isolation Forest curé PR-AUC 0.91, service :8091) + monitor GPS live G3 ✅. KPIs dashboard ✅** |
| S13 | 05-11/08 | 🔄 | **Tests e2e ✅ (`e2e_integration_test.py` 8/8). Reste : déploiement, documentation** |
| **S13+** | **27/07** | **✅** | **App mobile PARENT Flutter (`frontend/parent-mobile/`, Chrome :5174 / Android) : 5 écrans miroir de l'espace parent web (login, Mon espace+countdown, carte live glisse GPS, messagerie, notifications, assistant MS9), Material 3 clair+sombre, skeletons, perf (RepaintBoundary/const/builder). Aucun delta backend. Skills `flutter-ui-ux`/`flutter-tester` + agent `flutter-expert` installés.** |
| **S14** | **19/08** | **✅** | **ETA « le long de la tournée » (5 écrans) + garde anti-extrapolation MS12 + page Prévisions parent (web `/parent/eta` + mobile 6ᵉ onglet, MS5 `/mes-enfants` scopé JWT) + fix présence figée + refonte page de connexion (2 bugs thème sombre) + migration LLM forcée (Llama décommissionné → gpt-oss)** |
| **S15** | **20/08** | **✅** | **App mobile CHAUFFEUR Flutter (`frontend/chauffeur-mobile/`, Chrome :5175 / Android) : 7 écrans miroir de l'espace chauffeur web, le téléphone devient la **source GPS réelle** (foreground service, m/s→km/h), **file d'écritures hors ligne persistée** (FIFO, fusion des présences, réconciliation des démarrages non idempotents), démarrage refusé sans itinéraire (protège la détection de déviation MS11), `ApiClient` injectable → **55 tests** dont les écrans à actions. Aucun delta backend.** |
| **S15** | **22/08** | **✅** | **Campagne de correction issue de l'exécution contre le backend réel : (1) ETA « cycle fermé » — le compte à rebours bondissait de 1,1 à 35,4 min pile à l'arrivée à l'école — corrigé dans les **3 implémentations** (`routeEta` Dart ×2 + TS) et les **6 écrans** ; (2) MS5 `continue_straight=false` — `geometrie` et `distance_m` décrivaient deux trajets (+10,92 %), convergence ramenée à 0,05 %, référence de déviation MS11 assainie ; (3) figeage de l'écran « Prévisions » (ListView imbriqué) ; (4) crash au `dispose` des cartes (`late final AnimationController`) ; (5) couverture chauffeur portée à 84 tests (shell + 3 écrans de consultation), parent à 25.** |
| **S15** | **25/08** | **✅** | **MS4 — canal de notifications poussées branché (`docs/MS4_NOTIFICATIONS_FCM.md`). Diagnostic de 10 157 échecs → 4 bugs masqués corrigés : rafale `BUS_ARRIVE_ECOLE` (150 notifs/parent → 1), une ligne par événement, enregistrement idempotent (HTTP 500 à la 2ᵉ connexion), journal paginé côté serveur. `parent-mobile` équipée (web + Android), spike Gradle concluant. Reste : `web-admin`, `chauffeur-mobile`, téléphone physique.** |
| **S15** | **26/08** | **✅** | **Recette finale de bout en bout (`docs/RECETTE_FINALE.md`, `scripts/recette/`) : 8 phases rejouables contre la stack vivante. Confirme 7 correctifs (MS5 0,05 % · churn 0 % · masque MS13 · propagation 2,30 s · verrou d'arrivée 30 pings→1/parent · jeton FCM idempotent · cascade MS9 servie) et **27 routes web-admin rendues sans erreur console dans un vrai Chrome**. Trouve **20 défauts**, dont **2 critiques** : auto-promotion ADMIN via `/register` (exploitable sur 6 surfaces/6) et **301 élèves + domiciles GPS servis sans authentification** — ce dernier était détecté par l'assertion Newman n° 13, jamais rejouée.** |
| S14-S15 | 12-25/08 | ⏳ | Mémoire, Slides, Vidéo démo, Soutenance |

---

## 🔜 Prochaine étape

1. **MS9 — Chatbot LLM parents (UC-10)** : ✅ **livré (Phase A)** — agent tool-calling maison, agnostique Groq/Gemini
   (cascade 70b→8b→Gemini), FR/AR/darija, outils MS2/MS3/MS12/MS1/MS10 scopés au parent, reverse geocoding OSM.
2. **NL2SQL admin (UC-11)** — ✅ **Phase B livrée** : question langage naturel → SQL PostgreSQL (schéma DDL en
   prompt) → exécution **read-only** (rôle Postgres `ms9_readonly` + transaction `READ ONLY`) → synthèse.
   Page admin `AdminAssistant.tsx` affichant réponse, SQL généré et tableau.

**Puis (CDC restant) :** Dashboard admin (UC-13), réaffectation dynamique (UC-9), app Flutter parent/chauffeur.

**Chaînons d'intégration encore ouverts (audit) :** G2 persistance des tournées (entité Circuit/Arrêt → ETA par arrêt),
G4 réaffectation dynamique, G6 `clustering.updated`→MS5 re-plan, G7 boucle de feedback ML (durées réelles→historique),
canal de **notification admin** (MS4 ne pousse que par parent/bus).

---

## ⚠️ Points d'attention (à jour)

1. **Convertisseur RabbitMQ MS4** : les producteurs doivent publier en **`text/plain`** (le `Jackson2JsonMessageConverter`
   de MS4 rejette un `application/json` objet dans les handlers `String`). Corrigé pour MS12 (`eta.bus.arriving`) ; les
   producteurs Java publient déjà des Strings.

2. **Contrainte DB `notifications_type_check`** : Hibernate (`ddl-auto=update`) **ne met pas à jour** la contrainte CHECK
   quand on ajoute une valeur d'enum (`ENFANT_A_BORD`). Sur une base **existante** → `ALTER TABLE notifications
   DROP/ADD CONSTRAINT` avec la liste complète ; une base **fraîche** la crée correctement.

3. **FCM** : Firebase est **configuré** (`firebase-service-account.json` présent). Les tokens de démo invalides →
   `ECHEC` en DB (normal ; la notif est bien historisée). Sans device token → notif ECHEC « aucun device » (historisée).

4. **Données de démo** : `generer_comptes.py` (idempotent, option `--reset`) crée parents/fratries + chauffeurs + bus,
   exporte `comptes_utilisateurs.csv/json` (**gitignorés**, mots de passe en clair — dev only). `parentId`/device token
   requis pour que les notifs atteignent un parent.

5. **JWT_SECRET** : identique partout (`app.jwt.secret` MS7 = `.env` des services Python). **CORS** : uniquement la Gateway.

6. **Python 3.11 (env conda `nlp`)** : `scikit-learn==1.5.2`, `aio-pika==9.4.1` ; services Python démarrés via `start-all-ms.bat`.

7. **Modèles LLM — durée de vie courte, chez TOUS les fournisseurs. Épingler des alias, pas des versions.**
   *(19/08)* Groq a décommissionné **toute la famille Llama** le 16/08 (`llama-3.3-70b-versatile` **et**
   `llama-3.1-8b-instant`, alors que l'avis ne citait que le 70b). La cascade MS9 échouait deux fois avant de
   retomber sur Gemini, **sans erreur visible**.
   *(23/08, trouvé par le benchmark MS9)* **Le repli Gemini est mort à son tour** : `gemini-2.0-flash` renvoie
   **404 sur 100 % des appels** — la clé est valide, mais **aucun modèle « 2.0 »** ne figure parmi les 51
   servis par `GET /v1beta/openai/models`. Le **3ᵉ et dernier étage de la cascade** était donc hors service, et
   personne ne l'avait vu : MS9 ne s'en aperçoit que si les deux étages Groq saturent en même temps — auquel
   cas il renvoie 503 au lieu de dégrader.
   **Leçon générale** : viser un **alias** (`gemini-flash-latest`, testé 200) plutôt qu'une version figée
   (`gemini-2.0-flash`) ; un alias survit par construction aux renouvellements de génération.
   **Vérifier `GET https://api.groq.com/openai/v1/models` ET `GET
   https://generativelanguage.googleapis.com/v1beta/openai/models` avant toute démo** — et se rappeler que
   `ms9-llm/.env` **écrase** les valeurs de `config.py`. Un simple appel à `/models` par fournisseur au
   démarrage de MS9 transformerait cette panne silencieuse en avertissement au log.

8. **`--surface-deep` ≠ `--header` (web-admin)** : `--header` est une **encre de titre**, elle s'éclaircit en thème
   sombre. L'utiliser comme **fond** sous du texte blanc donne du blanc sur clair. Pour toute surface de marque
   foncée, utiliser **`--surface-deep`** (reste foncé dans les deux thèmes).

9. **ETA : ne jamais viser un point en distance directe pendant une tournée.** La tournée boucle
   `école → élèves → école` : un ETA point-à-point **augmente** pendant le ramassage. Utiliser `routeEta.ts` /
   `route_eta.dart` (distance restante **sur** la polyligne). Et côté MS12, ne pas dépasser le domaine
   d'entraînement (tronçons 0,7–4 km) : la garde `facteur_contexte` s'en charge.

10. **Unité de vitesse GPS : km/h partout.** `bus_simulator.py` publie des **km/h** (40 normal, 110 anomalie) et
    le seuil MS11 `SEUIL_VITESSE_KMH` vaut 90. `geolocator` (app chauffeur) renvoie des **m/s** → conversion
    ×3,6 dans `gps_emitter.dart`. Sans elle, aucune anomalie de vitesse ne se déclencherait depuis un vrai
    téléphone, et l'affichage divergerait entre bus simulés et bus réel — **sans erreur visible**.

11. **Deux sources GPS pour un même bus se contredisent.** L'interrupteur « Transmettre ma position » de l'app
    chauffeur est OFF par défaut. Pour une démo au simulateur, le laisser OFF ; pour démontrer le GPS réel,
    couper `bus_simulator.py` sur ce bus.

12. **Ne jamais démarrer un trajet sans `geometrie`.** MS1 l'accepte (le champ est optionnel) et MS11 se
    retrouve alors sans route de référence : `DEVIATION_ITINERAIRE` ne peut plus se déclencher, **silencieusement**.
    L'app chauffeur refuse donc le démarrage plutôt que de partir à l'aveugle, et met la géométrie en cache local
    pour rester capable de démarrer hors ligne.

13. **La tournée est un cycle FERMÉ : recaler un bus dessus exige de mémoriser sa progression.** ✅ **corrigé
    partout (22/08)**. Mesuré sur les données réelles du groupe 1 : le premier et le dernier point de la
    polyligne sont à **0,0 m** l'un de l'autre. Quand le bus revient à l'école, sa position se projette aussi
    bien sur le début que sur la fin — et à égalité d'écart, c'est le **début** qui gagne. Conséquence chiffrée :
    à 98 % du parcours il reste 1,1 min, à 99 % il « reste » **35,4 min**. Le compte à rebours bondit à l'instant
    de l'arrivée, sous les yeux des familles. Correctif : `depuisAlongM` (abscisse déjà atteinte, réinjectée d'un
    calcul au suivant) — un bus ne rembobine pas sa tournée. Après : 0,6 min à 99 %, 0,0 min à l'arrivée.
    Appliqué aux **3 implémentations** (`chauffeur-mobile`, `parent-mobile`, `web-admin/routeEta.ts`) et aux
    **6 écrans** concernés. ⚠️ **Le plancher est PAR BUS côté parent** (`Map<int,double>` / `Record<number,number>`) :
    la progression appartient au bus, pas à l'élève ; deux enfants d'une même famille peuvent partager le bus.
    Il est remis à zéro **au changement de polyligne uniquement** — surtout pas quand un élève monte, ce qui
    rouvrirait le bug au moment même de l'embarquement.

14. **MS5 : `distance_m` et `geometrie` décrivaient deux trajets différents (+10,92 %).** ✅ **corrigé (22/08)**.
    `distance_m` vient de la matrice OSRM `/table` ; `geometrie` venait de `/route` appelé sans
    `continue_straight=false` — OSRM imposait alors de franchir chaque waypoint tout droit et insérait des
    demi-tours. Mesuré contre l'OSRM local sur les 52 waypoints réels :
    `sans = 19 123,5 m / 42,23 min / 882 pts` · `avec = 17 241,1 m / 35,99 min / 753 pts` ·
    `matrice /table = 17 241,1 m / 35,99 min`. Vérifié avec un haversine de référence que l'écart ne venait
    **pas** de la projection équirectangulaire (0,008 %). Après correctif, convergence à **0,05 %**.
    Deux conséquences levées : (a) l'ETA était gonflé de 11 % ; (b) **la référence de déviation de MS11**
    contenait des demi-tours inexistants. *(Les clients dérivent malgré tout la vitesse de la polyligne qu'ils
    mesurent — immunité si la divergence revient.)*

15. **Ne jamais écrire `late final AnimationController _x = AnimationController(vsync: this, …)`.** Un `late
    final` n'est évalué qu'au **premier accès**. Si l'écran ne rend jamais la partie animée (chauffeur sans bus,
    enfants sans bus assigné, erreur de chargement), ce premier accès est celui de `dispose()` — qui construit
    alors un `Ticker` sur un élément déjà désactivé et lève *« Looking up a deactivated widget's ancestor is
    unsafe »*. Le crash survient en **quittant** l'écran, ce qui le rend difficile à rattacher à sa cause.
    Créer le contrôleur dans `initState`. Trouvé par un test, présent dans les `map_screen.dart` des **deux**
    apps Flutter, corrigé dans les deux.

16. **Benchmarker le code qu'on déploie, pas celui qu'on a écrit dans un notebook.** Le défaut le plus
    coûteux trouvé le 23/08, et il touchait **trois briques sur cinq** : MS6 comparait dix algorithmes
    euclidiens sans que le k-médoïdes **routier** déployé y figure ; MS11 benchmarkait le détecteur qui tourne
    *à la demande* pendant que les **règles live**, seules à tourner en continu, n'avaient aucune métrique ;
    MS12 publiait un MAE de tronçons alors que le service répond en mode **`facteur_contexte`**. La question
    qui les a révélés n'est pas « quel notebook ai-je écrit ? » mais **« quel code s'exécute quand un parent
    ouvre l'application ? »**. Détail : les trois trous étaient *documentés* — MS12 disait même dans son
    docstring que ses métriques n'y valaient plus rien.

17. **`DEVIATION_ITINERAIRE` est structurellement peu sensible sur une tournée dense — mesuré.** La règle
    compare la position au point le plus proche de **toute** la polyligne. Une tournée de 50 arrêts repassant
    dans le même quartier, un bus décalé de 400 m reste en moyenne à **174 m** de sa propre tournée : un
    détour de 250 m n'est détecté que sur **9,6 %** du parcours, 400 m sur 35,8 %. **C'est le piège n° 13
    (cycle fermé), corrigé pour l'ETA par `depuisAlongM` et jamais transposé ici.** En attendant, le seuil
    de **250 m est trop haut** : à 120 m la couverture double **sans aucune fausse alarme** jusqu'à σ=30 m de
    bruit GPS (mesuré). Et `VITESSE_EXCESSIVE` n'a **aucun anti-rebond**, contrairement à la déviation : un
    seul ping aberrant déclenche une alerte critique.

18. **Un classement de modèles sur 8 positifs ne tient pas.** MS11 gelait `iforest_curated` (PR-AUC 0,9127)
    devant `seuil_surprise` (0,8043) sur un split unique de 30 jours contenant **8 anomalies**. Bootstrap :
    les intervalles de confiance se recouvrent largement. Validation glissante à 4 blocs (**38 positifs**) :
    **le classement s'inverse** (0,926 contre 0,847). Avant de défendre un gagnant, compter **combien
    d'observations le départagent**. *Contre-exemple utile, à connaître aussi :* sur MS12, l'écart de
    **2,7 secondes** entre ElasticNet et Ridge, qui semblait être du bruit, s'est révélé **significatif** —
    le bootstrap **apparié** compare les erreurs sur les mêmes trajets et l'écart y est systématique.
    L'incertitude ne va pas toujours dans le sens qu'on croit : il faut la mesurer, pas la supposer.

19. **MS6 : le nombre de bus dépendait de l'ORDRE des lignes renvoyées par PostgreSQL.**
    ✅ **CORRIGÉ le 24/08** (`selection.py`, `clustering.py`, `etat.py` — 63 tests).
    *Après correctif : **k = 7 sur 30 permutations sur 30, et une seule partition distincte** ;
    churn moyen par inscription **7,24 % → 2,49 %**, médian **6,42 % → 1,02 %**, et **0 changement
    de flotte** au lieu de 9. Vérifié de bout en bout via le vrai `get_all_eleves()` de MS2 :
    ordre MS2 et ordre inversé donnent des affectations **identiques élève par élève**.*
    ⚠️ **Coût unique au déploiement : 22 élèves sur 300 (7,3 %) changent de bus au premier
    recalcul** — la partition livrée est désormais le meilleur de 5 redémarrages (silhouette
    0,405 → 0,4256). À faire à un moment où les familles peuvent être prévenues.
    *(Diagnostic d'origine, conservé pour mémoire :)*
    Sur **30 permutations** des mêmes 300 élèves, même graine, même matrice OSRM :
    **k=7 dans 57 % des cas, k=8 dans 7 %, k=9 dans 37 %.** Deux bus et deux chauffeurs d'écart, sans
    qu'aucune donnée métier n'ait bougé. *(`ms6-clustering/data/sensibilite_ordre.json`.)*
    - **Cause racine** : `choisir_k` prend l'**argmax** des silhouettes du Pareto, or celles de k=8 et
      k=9 ont un bruit d'initialisation (±0,012 et ±0,020) **supérieur aux écarts qui les séparent**
      (0,006 à 0,017). C'est un argmax sur du bruit ; l'ordre des lignes ne fait que tirer les dés.
    - **Pourquoi l'ordre n'est pas stable** : `EleveService.listerTous()` fait `repo.findAll()` **sans
      `ORDER BY`** → ordre du tas. Et MS6 **réécrit les 300 lignes** par bulk update à chaque
      application, ce qui change ce tas. **Appliquer un clustering peut donc changer le k du suivant.**
      Comme MS6 recalcule sur `eleve.created`, **chaque inscription en cours d'année rejoue la loterie**
      et peut faire changer de bus des enfants dont rien n'a changé.
    - **Ce que ça coûte quand on inscrit un élève** (mesuré de 270 à 300 élèves, `stabilite.py`) :
      avec la règle actuelle, `k` change **9 fois sur 15 inscriptions** et **12 à 13 % des élèves
      changent de bus à chaque bascule** — une trentaine d'enfants déplacés pour une inscription.
    - **Correctifs, mesurés puis classés** :
      **(1) `choisir_k` robuste** — médiane sur plusieurs initialisations par `k`, puis **plus petit
      `k` à moins de ε ≈ 0,02 du meilleur**. Mesuré : **k=7 sur 15 permutations sur 15**, churn
      médian 6,42 % → 1,03 %. Donne k=7, donc **stabilise sans changer la sortie actuelle**.
      **(2) + hystérésis sur `k`** — ne changer de flotte que si l'ancien `k` est **infaisable** ou
      battu de plus de ε. Sans elle, la parcimonie saute sur tout `k` plus petit qui devient
      faisable (pic de churn à 25,4 % au franchissement de ⌈n/50⌉). **Avec (1), c'est la variante
      qui domine sur les trois métriques : churn moyen 2,25 % vs 7,24 %, max 8,03 % vs 13,27 %,
      2 changements de flotte vs 9.** Les deux se font ensemble.
      **(3) Canoniser l'ordre** dans `production_clustering` (côté MS6). ⚠️ **Fait seul, (3)
      figerait k=8** — l'ordre trié par id tombe précisément sur le k le plus rare (7 %).
      **(4) Publier le churn** comme métrique de production : c'est ce que les familles subissent.
      ~~Amorçage à chaud~~ — **proposé, mesuré, retiré** : 0,7–2,7 % de churn contre 0,0–1,7 % à
      froid. Le churn ne vient pas de la dérive des médoïdes, il vient du changement de `k`.
    - **Leçon de méthode** : le benchmark exécutait la vraie fonction de production **sans emprunter
      le chemin de production** (CSV trié au lieu de MS2). C'est le piège n° 16 retourné contre l'outil
      de mesure lui-même. Un benchmark doit consommer **la même source de données que le service**.
    - **Trois erreurs de conception commises pendant le correctif, toutes attrapées par la mesure** —
      à retenir si on retouche `selection.py` :
      **(a) ε global.** Première version : ε = plus grande dispersion de *tous* les candidats. Un
      `k=9` très instable élargissait la marge au point de faire passer `k=6` pour l'égal de `k=7`.
      → ε doit être **propre à la comparaison** (les deux candidats concernés, pas un troisième).
      **(b) Meilleur essai pour comparer.** Prendre le meilleur de N par `k` favorise
      **mécaniquement le plus bruité** (on compare des maxima d'échantillons de variances
      différentes) : le service répondait alors k=9 dans **14 cas sur 30**. → **médiane pour
      comparer les `k`**, **meilleur essai pour la partition livrée** une fois `k` choisi.
      **(c) Une seule marge pour deux questions.** ε statistique (« ces deux `k` sont-ils
      discernables dans ce calcul ? », ~0,005) ≠ marge d'hystérésis (« ce gain justifie-t-il de
      redistribuer toute l'école ? », 0,03). Avec la seule marge statistique, l'hystérésis ne se
      déclenchait jamais : un écart de 0,019 entre 292 et 296 élèves suffisait à faire basculer la
      flotte de 7 à 9 puis revenir. Le MAD n'y aidait pas — il vaut **0** sur une distribution
      bimodale dont trois essais sur cinq sont dans le même mode.

20. **MS6 : le garde-fou qualité était bloqué en DEGRADE depuis cinq semaines — un cliquet.**
    ✅ **CORRIGÉ le 24/08** (`quality.py`, 12 tests dans `tests/test_qualite.py`).
    `maybe_maj_baseline` ne réécrit la référence **que si le verdict est OK** (`quality.py:151`).
    Une référence trop haute rend donc tout run `DEGRADE`… ce qui l'empêche d'être mise à jour :
    **trop haute → DEGRADE → jamais réécrite → toujours trop haute.** Constaté : référence à
    **0,5183** écrite le **17/07** sur un jeu à **14 dispersés**, utilisée jusqu'au 24/08 pour juger
    des runs à **17 dispersés** et à un niveau réellement atteignable de 0,4334. Cinq semaines de
    DEGRADE permanent, sans qu'aucune dérive réelle n'ait eu lieu.
    - **Correctif 1 — plafond** : la référence ne peut jamais **dépasser l'ancre** (le point de
      conception gelé). Elle peut descendre — la détection de dérive continue de fonctionner —
      mais un run exceptionnellement bon ne redéfinit plus ce qui est atteignable.
    - **Correctif 2 — contexte** : la référence enregistre `n_eleves`, `capacity`, `rayon_max_m`.
      Un changement de **capacité** ou de **rayon** la rend inapplicable (paramètres structurels :
      ils redéfinissent le problème). L'effectif, lui, bouge naturellement et n'invalide pas.
    - **Correctif 3 — grandeur comparable** : l'ancre était `silhouette_routier` = 0,43336, mesurée
      sur le **cœur** (283 élèves), alors que le service publie la silhouette de la partition
      **complète** (300). Deux grandeurs différentes comparées l'une à l'autre. Ajout **non
      destructif** de `silhouette_partition_complete` = 0,4256 dans `production_config.json` (la
      valeur historique est conservée, elle est citée dans la documentation).
    - ⚠️ **Ne PAS « écrire la référence même sur DEGRADE »** — c'est la correction qui vient à
      l'esprit en premier, et elle **détruit le garde-fou** : chaque run serait comparé au précédent
      légèrement moins bon, donc une dérive lente ne déclencherait jamais rien. La grenouille qu'on
      fait bouillir.
    - **Vérifié en production** : verdict **OK**, aucune raison, plancher 0,3192, référence
      0,4256 avec son contexte. *Ancien fichier conservé :
      `data/quality_baseline.json.perimee-17-07.bak`.*

21. **Centraliser une configuration crée trois façons neuves de casser la production — toutes
    silencieuses.** Les trois ont été trouvées en exécutant MS13 contre le vrai backend, aucune
    par relecture du code. À relire avant de toucher à `params.py`, à `ParametresCache` ou au
    formulaire.
    - **(a) Un masque renvoyé n'est pas une valeur.** Le formulaire reçoit `••••••4f2a` depuis
      `GET /api/parametres` et le conserve dans son état. L'administrateur modifie un tout autre
      champ du même onglet, enregistre — et le masque part avec le lot. Vérifié avant correctif :
      **la clé API était remplacée par des puces, HTTP 200**, sans erreur nulle part. La garde est
      **côté serveur** (`valider()` refuse toute valeur commençant par `•`) et non dans le
      formulaire : elle doit tenir pour un client mobile, un script ou un `curl`.
    - **(b) « Absent » ne veut pas dire « à effacer ».** MS13 démarre avec ses secrets vides — un
      secret n'a pas de défaut dans le catalogue. Au premier démarrage après branchement, MS9 a
      donc remplacé ses clés Groq **et** Gemini, pourtant valides et lues de son `.env`, par des
      chaînes vides ; l'assistant serait tombé au premier message parent avec pour seule trace un
      « mode dégradé » au journal. Règle retenue : **le `.env` est l'amorçage, MS13 ne prend le
      dessus que s'il a effectivement une valeur** (`if valeurs[cle] == "" and actuel != "": continue`).
      Corollaire : on ne vide pas un réglage textuel depuis la console, on passe par le `.env`.
    - **(c) Une fausse alerte est pire que pas d'alerte.** `models-check` comparait les
      identifiants tels quels : Groq renvoie `openai/gpt-oss-120b`, mais Gemini renvoie
      `models/gemini-flash-latest` quand on l'appelle avec `gemini-flash-latest`. **Tous** les
      modèles Gemini étaient donc déclarés morts. Un outil de diagnostic qui crie au loup envoie
      corriger une panne inexistante, puis n'est plus cru le jour où la panne est réelle. Préfixe
      normalisé, et la distinction re-vérifiée **dans les deux sens** (l'alias passe OK, le
      `gemini-2.0-flash` réellement retiré reste signalé).
    - **Fil conducteur** : dans les trois cas, le système faisait *exactement ce qu'on lui avait
      demandé* — écrire la valeur reçue, appliquer la configuration centrale, comparer deux
      chaînes. Aucune exception, aucun code d'erreur. C'est le propre d'une couche de
      configuration : elle ne plante pas, elle applique.

22. **Une file durable partagée ne convient PAS à un événement de configuration.** RabbitMQ
    distribue les messages d'une file en tourniquet entre ses consommateurs : avec une file
    durable commune, **un seul** service recevrait chaque `parametres.updated` et les autres
    resteraient sur d'anciennes valeurs — une flotte configurée de façon incohérente, sans
    aucune erreur. Les services Python déclarent donc chacun une file **exclusive et
    auto-supprimée** (`declare_queue("", exclusive=True, auto_delete=True)`). MS4 fait
    l'inverse — file **durable** `ms4.parametres.queue` — parce qu'il est unique et qu'il doit
    rattraper un changement survenu pendant son redémarrage.

---

23. **Un canal jamais branché ne signale pas son absence — il signale un échec, ce qui n'est pas
    pareil.** MS4 historisait 100 % de ses notifications en `ECHEC` (« Aucun device FCM
    enregistré ») depuis toujours. Le tableau de bord était rouge en permanence, donc **plus
    personne ne le regardait** : l'alerte permanente est équivalente à l'absence d'alerte
    (même mécanique que le cliquet du piège n° 20 et la fausse alerte du n° 21c). Et surtout,
    cet échec **masquait quatre bugs** qui se seraient tous déclenchés le jour du branchement —
    dont une rafale de **150 notifications par famille en trois minutes**. **Un statut d'échec
    structurel doit être distingué d'un échec réel**, sinon il devient un tapis sous lequel
    s'accumulent les vrais défauts.

24. **Ce qui n'est jamais exercé n'est pas « qui marche », c'est « dont on ne sait rien ».**
    Trois des quatre bugs trouvés ici étaient dans du code écrit depuis des mois et jamais
    parcouru : la boucle d'envoi multi-appareils (jamais plus d'un appareil… puisque zéro),
    la réinscription d'un jeton (jamais deux fois… puisque jamais une), la rafale d'arrivée
    (jamais visible… puisque rien n'était livré). Le cas de la contrainte **UNIQUE** sur
    `fcm_token` est le plus net : le code désactivait la ligne existante *sans la supprimer*
    puis en insérait une nouvelle avec le même jeton — **HTTP 500 à la deuxième connexion du
    même appareil**, c'est-à-dire dans le cas *normal*, un jeton FCM étant stable par
    installation. ⚠️ **Corollaire de méthode** : avant de brancher un canal resté inerte,
    relire ce qu'il fait quand il reçoit *plus d'un* élément — c'est là que se logent les
    hypothèses jamais mises à l'épreuve.

25. **`firebase_core` applique l'ancien plugin Kotlin (KGP) — sursis, pas feu vert.** L'APK se
    construit sur **AGP 9.0.1 / Gradle 9.1 / Kotlin 2.3.20** (53,4 Mo, vérifié), mais Flutter
    avertit : *« Your app uses plugins that apply Kotlin Gradle Plugin (KGP) […] future versions
    of Flutter will fail to build »*. C'est la même famille que le ticket FlutterFire
    [#17987](https://github.com/firebase/flutterfire/issues/17987) (qui ne visait que
    `firebase_analytics` et `firebase_performance` — d'où le choix de n'ajouter **ni l'un ni
    l'autre**), et la même famille que l'épinglage de `path_provider_android: 2.2.17` contre
    `jni`. Échappatoire connue si le blocage survient : `android.builtInKotlin=false` +
    réintroduction manuelle de `kotlin-android`, **temporaire** (retirée avant AGP 10).
    À revérifier à chaque montée de Flutter ou d'AGP.

26. **Sur le web, deux fichiers manquants font échouer FCM *en silence*, et différemment.**
    Sans **clé VAPID**, `getToken()` renvoie `null` — aucun jeton, donc aucune inscription.
    Sans **`web/firebase-messaging-sw.js`**, le jeton est obtenu normalement mais **aucun
    message n'est jamais délivré** ; l'erreur trompeuse *« unsupported MIME type
    ('text/html') »* signifie seulement que le fichier est absent et que le serveur de dev
    renvoie `index.html` à sa place. Aucun des deux n'est un secret (clé publique d'un côté,
    fichier servi au navigateur de l'autre) — les mettre dans les secrets MS13 serait une
    perte de temps. Et **aucune empreinte SHA-1 n'est requise** pour FCM : elle sert à Google
    Sign-In, aux Dynamic Links et à l'auth par téléphone. C'est le principal gouffre de temps
    de cette configuration.

27. **Un jeton FCM identifie un appareil, jamais une personne — et sur le web, une *origine*.**
    Le jeton est lié au couple *origine + service worker*. La console web servant les **trois
    rôles sur `localhost:5173`**, admin, parent et chauffeur y **partagent le même jeton** :
    une seule application Firebase suffit pour les trois espaces, et un changement de rôle sur
    le même navigateur **réaffecte** le jeton au lieu d'en créer un. D'où deux règles :
    réenregistrer à **chaque** connexion (c'est ce qui réaffecte), et détacher le jeton
    **avant** d'effacer le JWT à la déconnexion (l'appel est authentifié). Corollaire de
    développement : `flutter run -d chrome` crée un **profil de navigateur temporaire**
    (vérifié dans `flutter_tools/lib/src/web/chrome.dart`), donc autorisation et jeton sont
    remis à zéro à chaque lancement et les jetons morts s'accumulent —
    `--web-browser-flag=--user-data-dir=…` est désormais dans les quatre lanceurs VS Code.

28. **Un test désactivé est pire qu'un test absent : il rend le rapport vert.**
    Trouvé le 26/08 par la recette finale. Cinq `pom.xml` portent
    `<skipTests>true</skipTests>` — **ms1-bus, ms2-eleves, ms3-localisation, ms7-auth,
    ms8-gateway**. `mvnw.cmd test` affiche `Tests are skipped.` puis **BUILD SUCCESS**, et
    le total réel est **18 tests** (MS4 17 + MS10 1), pas les 22 annoncés. Les quatre
    modules qui portent l'**authentification**, la **passerelle**, les **élèves** et les
    **bus** n'exécutent donc aucun test — et rien ne le dit. Même famille que le n° 23 :
    un signal toujours vert vaut absence de signal. **Compter les tests exécutés, jamais
    se fier au code de sortie.**

29. **Un test de sécurité qu'on ne rejoue plus finit par documenter une faille.**
    La collection Newman contient depuis toujours l'assertion 13, *« Eleves endpoint
    without token returns 401 »*. Rejouée le 26/08 : **87/88**, et l'assertion cassée est
    **celle-là**. `GET /api/eleves` a été passée `permitAll` dans MS2 — vraisemblablement
    pour que MS5, qui n'a pas de jeton utilisateur, puisse lire les élèves — et
    **301 enfants avec nom, prénom et coordonnées GPS de leur domicile** sont depuis servis
    sans authentification sur `:8082`. Le garde-fou existait, il avait fonctionné, personne
    ne l'écoutait plus. Corollaire : **le 88/88 n'avait aucun lanceur** (`scripts/recette/newman.cmd`
    y remédie) — un chiffre que personne ne peut rejouer cesse d'être une garantie.
    ⚠️ Même famille, plus grave encore : `POST /api/auth/register` est `permitAll` **et**
    lit `role` dans le corps. Une requête anonyme suffit à obtenir un jeton **ADMIN** ;
    vérifié exploitable sur **6 surfaces d'administration sur 6**, NL2SQL compris.

30. **Autoriser un rôle ne suffit pas s'il échoue au contrôle de propriété qui suit.**
    `POST /api/trajets/{id}/terminer` est annoté `hasAnyRole('CHAUFFEUR','ADMIN')`, mais le
    service exige ensuite `trajet.chauffeurId == principal.userId` : l'ADMIN reçoit
    **400 « Ce trajet n'appartient pas à ce chauffeur »**. L'autorisation est **creuse**.
    Conséquence opérationnelle, rencontrée pour de vrai pendant la recette : le démarrage
    étant **non idempotent**, un trajet resté `EN_COURS` (téléphone HS, chauffeur parti)
    **bloque le bus définitivement, sans aucun recours par l'API**. Le symétrique existe
    côté front : `/carte` (`App.tsx:63`) n'a **aucun** garde de rôle — un parent d'un seul
    enfant y voit **14 positions GPS et les 10 bus de la flotte**.
    Règle : **RBAC et contrôle de portée sont deux couches ; vérifier les deux ensemble,
    par rôle, contre le service en fonctionnement** — la lecture du code ne les croise pas.

31. **Un test dont le résultat dépend de la météo n'est pas un test.**
    `e2e_integration_test.py` (G1) pousse une position et attend `BUS_EN_ROUTE`, publiée si
    l'ETA ≤ 10 min. Mesuré le 26/08 : **10,06 min** — échec de **3,6 secondes**. La position
    est à 3 595 m, durée OSRM 6,47 min, mais le contexte du jour (nuageux · trafic dense ·
    jour de souk) l'a portée au-dessus du seuil. Le « 8/8 » historique tenait au calendrier.
    **La chaîne est intacte** — prouvé séparément : à 2 214 m (ETA 6,74 min) la notification
    arrive en **3 secondes**. Corollaire de méthode : un test d'intégration doit **figer son
    contexte** (`auto_context=false`) ou se placer loin du seuil ; sinon il mesure le temps
    qu'il fait. Deux voisins de la même famille : `e2e_integration_test.py` **ne démarre pas**
    sur une console Windows par défaut (emoji en cp1252 → `UnicodeEncodeError`), et
    `pytest ms6-clustering/tests` **échoue depuis la racine** (le `.env` racine est absorbé
    par pydantic-settings qui interdit les champs surnuméraires) — or c'est la commande que
    prescrivent les docstrings. **Un script de vérification doit démarrer chez le lecteur.**

32. **Un contrôle d'AUTORISATION n'est pas un contrôle de PORTÉE — et un harnais qui ne
    teste que le premier laisse passer une faille par endpoint.**
    La recette du 26/08 vérifiait 45 combinaisons rôle × route et les trouvait correctes. Une
    revue de code ciblée sur les **interactions entre acteurs** a ensuite trouvé **13 failles
    de plus**, toutes du même moule : la route était ouverte au bon *rôle*, et n'importe quel
    compte de ce rôle agissait sur les données de n'importe quel autre. Un chauffeur pointait
    l'élève d'un collègue — ce qui envoie une notification au parent d'une **autre** famille.
    Un parent lisait la **polyligne** d'un autre bus, c'est-à-dire la rue de chaque famille
    transportée : exactement ce que MS5 refuse délibérément de livrer via `/mes-enfants`, et
    que MS1 donnait gratuitement.
    **Trois enseignements** : (a) tester chaque interaction sur ses **deux faces** —
    *l'acteur légitime peut*, *l'acteur voisin ne peut pas* ; (b) écrire le harnais **avant**
    de corriger, pour qu'il parte rouge et que la non-régression soit acquise par
    construction ; (c) le motif correct existait déjà dans le projet (`verify_parent` de MS5,
    `_check_scope` de MS9) — il n'avait simplement pas été appliqué partout.
    ⚠️ Le **WebSocket GPS** reste dans cet état : aucun jeton, origine `*`, filtre « tout »
    par défaut. Il alimente les trois frontends, donc le corriger est un chantier transverse.

33. **Un `@ExceptionHandler(RuntimeException.class)` avale les statuts HTTP explicites.**
    Après déploiement des contrôles de portée, tous les refus sortaient en **400** au lieu de
    **403**. `ResponseStatusException` hérite de `RuntimeException` : le gestionnaire global,
    plus large, l'attrapait et écrasait le statut choisi par le code. Le refus fonctionnait —
    seul le code de retour mentait, et le client ne pouvait plus distinguer un accès refusé
    d'une requête mal formée. Un `@ExceptionHandler(ResponseStatusException.class)`, **plus
    spécifique**, restaure le statut. À vérifier dans tout service qui attrape largement.

34. **Une suite de tests peut dépendre de la faille qu'on vient de fermer.**
    Le correctif d'auto-promotion ADMIN a fait tomber Newman de **87/88 à 57/88**. Motif :
    la collection créait son propre administrateur par `POST /api/auth/register` avec
    `role: "ADMIN"` — elle **exploitait l'escalade de privilège pour se dérouler**. Le
    réflexe (« rafistoler pour que ça repasse ») aurait été le mauvais. La collection a été
    réorientée : l'admin vient du compte seedé, le chauffeur est créé par
    `POST /api/auth/users`, et les requêtes 01 et GW-02 deviennent des **garde-fous** qui
    envoient `role: "ADMIN"` et vérifient qu'on obtient **PARENT** — en direct et à travers
    la passerelle. Retour à **88/88**, en testant le correctif au lieu d'en dépendre.
    **Quand un correctif casse des tests, se demander d'abord ce que ces tests supposaient.**

35. **Le contexte d'une référence qualité doit porter TOUT ce qui la rend comparable.**
    Le passage de 9 à 7 bus a fait rendre **DEGRADE** au garde-fou MS6 : *« compacité max
    +68 % vs référence »*. Normal — moins de bus ⇒ groupes plus étalés ⇒ compacité max plus
    grande, mécaniquement. Mais `reference_applicable` (`quality.py:75`) ne vérifie que
    `n_eleves`, `capacity` et `rayon_max_m` : **`k` n'y est pas**. Une référence écrite à k=9
    jugeait donc un run à k=7 sur une grandeur incomparable. Et comme la référence n'est
    réécrite **que** sur un verdict OK, le cliquet du piège n° 20 se réarmait sur une autre
    grandeur : le correctif de l'époque plafonne la **silhouette** à l'ancre, il n'y a pas
    d'équivalent pour la **compacité**. Contourné en réamorçant depuis le point de conception ;
    **le correctif de fond — inscrire `k` dans le contexte — reste à porter.**

36. **Deux chemins de calcul pour la même décision métier, avec deux algorithmes différents —
    et c'est le mauvais qui gagnait.**
    Trouvé le 27/08 **par l'usage**, pas par les tests : après une migration à k=7 bus,
    l'écran de clustering réaffichait 9 groupes dont un à **9 élèves sur 50 places**.
    `MS6` calcule l'affectation par deux voies : `POST /api/clustering/production`
    (déclenchée par l'administrateur) utilise la **distance routière OSRM**, celle du mémoire
    et du benchmark ; le **consumer RabbitMQ** — déclenché par `eleve.created`,
    `eleve.deleted`, `eleve.gps.updated`, `bus.created`, `bus.deleted` — utilisait la
    **distance euclidienne** (`use_road_for_auto = false`, « plus rapide »).
    Conséquence : **toute inscription, tout déménagement, toute suppression d'un élève de test
    repartitionnait les 300 élèves avec l'algorithme dégradé**, en écrasant la partition
    routière, la mémoire d'hystérésis (`last_selection.json`) **et** la référence qualité
    (`quality_baseline.json`). Une exécution de Newman suffisait — elle crée puis supprime un
    élève. C'est ce qui expliquait que `production_config.json` annonce k=7 pendant que la
    production restait obstinément à k=9 : **le piège n° 16 dans sa version la plus profonde**,
    les deux algorithmes coexistant et le moins bon l'emportant en silence.
    **Correctif** : aligner le drapeau aux **trois** endroits qui peuvent s'annuler —
    `config.py` (défaut du code), `.env` (amorçage), MS13 (`ms6.use_road_for_auto`, priorité,
    propagé à chaud).
    ⚠️ **Le réflexe de couper le recalcul automatique aurait été une erreur** : c'est une
    capacité annoncée du projet (déclencheur « ajout d'élève », S8), et la couper aurait
    retiré une démonstration. Une fois l'algorithme aligné, la vérification montre que le
    recalcul **se déclenche toujours et ne déplace plus personne** (churn 0 %, partition
    identique après création puis suppression d'un élève, Newman rejoué en entier à 88/88).
    On n'a pas eu à choisir entre la fonctionnalité et la stabilité — il fallait d'abord
    comprendre pourquoi elles semblaient s'opposer.
    **Leçon de méthode** : l'audit avait exercé le chemin manuel et l'avait trouvé correct.
    Aucun test ne créait puis supprimait un élève **en observant la partition**. Quand une
    même décision métier a deux points d'entrée, il faut les exercer **tous les deux** et
    comparer leurs sorties — sinon on valide celui qu'on regarde et on ignore celui qui écrit.

37. **Un consumer d'événements peut mourir en silence — et rien dans le service ne le dit.**
    Trouvé le 27/08 en vérifiant la justesse des briques IA. `ms11.gps.queue` avait
    **0 consommateur** : MS11 répondait « UP », `/live` renvoyait `200 {"n": 0}`, et **plus
    aucune anomalie n'était détectée** depuis un redémarrage — ni vitesse, ni arrêt prolongé,
    ni déviation. Un tampon vide est indiscernable d'une surveillance morte.
    **Deux causes, cumulées, présentes aussi dans MS12 et MS6** :
    (a) `asyncio.create_task(start_consumer())` **sans conserver la référence** — la
    documentation Python demande explicitement de stocker le résultat « pour éviter qu'une
    tâche disparaisse en cours d'exécution » ; le ramasse-miettes collectait le consumer avant
    son premier pas, symptôme caractéristique : `tentatives: 0`, la boucle n'avait pas même
    essayé ;
    (b) **aucune reprise** — `connect_robust` reconnecte une connexion *déjà établie* mais ne
    fait rien si la première tentative échoue, et les 13 services démarrent ensemble : MS11
    peut se présenter avant que RabbitMQ n'accepte les connexions. L'ancienne version
    attrapait l'exception, écrivait une ligne de journal, et laissait le service tourner sans
    consumer **définitivement**.
    **Correctif** : boucle de reprise à attente croissante + référence conservée + **état
    publié** (`surveillance_live` dans `/health`, `surveillance_active` dans `/live`).
    **Leçon de méthode** : `/health` répondait « UP » parce qu'il ne mesurait que ce que le
    service sait faire *sur demande*. Un service événementiel a deux moitiés — l'API et le
    consumer — et un health check qui n'en observe qu'une ment par omission. La règle
    générale : **tout ce qui écoute doit publier qu'il écoute.**

38. **Un élève fictif de test peut corrompre toutes les métriques d'un modèle.**
    Trouvé le 27/08. Le garde-fou qualité de MS6 rendait **CRITIQUE** : compacité maximale
    **145 893 m** (145 km) et silhouette tombée de 0,4256 à **0,298**. Le partitionnement
    était pourtant intact — churn 0, mêmes tailles. Seules les **métriques** étaient faussées,
    par un unique point aberrant : l'élève **« RBACTest », à 120,8 km de l'école**, quand les
    300 vrais élèves tiennent dans un rayon de **3,4 km**.
    Origine : la requête 36 de la collection Newman le crée pour vérifier qu'un CHAUFFEUR ne
    peut **pas** le supprimer — et le laisse donc en base **à chaque exécution**, avec des
    coordonnées choisies au hasard hors de la région.
    **Deux enseignements** : (a) une donnée de test qui survit à son test devient une donnée
    de production, et le clustering ne fait pas la différence ; (b) la silhouette et la
    compacité maximale sont des statistiques **sensibles aux extrêmes** — un point sur 301
    suffit à faire basculer un verdict. Corrigé des deux côtés : coordonnées ramenées dans
    Meknès, et suppression par la requête elle-même.
    ⚠️ Corollaire : toute suite de tests qui écrit en base doit **nettoyer ce qu'elle crée**,
    y compris — et surtout — les objets créés pour vérifier qu'ils ne peuvent PAS être
    supprimés. Ce sont précisément ceux que le scénario laisse derrière lui.

## 💡 Décisions architecturales clés

| Décision | Raison |
|----------|--------|
| JwtUtils = Java pur (pas @Component) | ms-common sans dépendance Spring |
| Double validation JWT (Gateway + MS) | Defense in depth |
| MS4→MS2 direct (pas via Gateway) | MS4 n'a pas de token utilisateur |
| Pas de @ManyToOne cross-service | Indépendance totale des bases de données |
| Bulk update au lieu de N PATCH | Anti-DDoS interne, 1 transaction PostgreSQL |
| **Projection UTM 30N (≠ StandardScaler)** | **Distance vraie en mètres à 33.9°N ; Silhouette interprétable** |
| **Distance routière OSRM (k-médoïdes)** | **La distance à vol d'oiseau sous-estime de 1.5–1.7× le trajet réel** |
| **Affectation capacitaire globale (LP)** | **Garantit taille de groupe ≤ capacité bus par construction** |
| **Capacité = paramètre uniforme** | **Tous les bus même taille, modifiable ; k = ⌈N/capacité⌉ dérivé (jamais fixé)** |
| **Choix du nb de bus par Pareto** | **Aide à la décision qualité vs flotte (pas un chiffre arbitraire)** |
| asyncio.Lock() sur recalcul | Évite burst de recalculs simultanés RabbitMQ |
| Tenacity retry (3 essais expo) | Résilience si MS2 redémarre pendant clustering |
| groupeId=999 pour bruit DBSCAN | Sentinel (legacy) ; en production les dispersés sont affectés au médoïde le plus proche |
| **CORS uniquement sur la Gateway** | **Retiré de MS1/MS2/MS3/MS6 (en-têtes en double = "Failed to fetch")** |
| Routes internes MS6→MS2 permitAll | MS6 Python ne gère pas de token Spring JWT |
| **File hors ligne FIFO stricte (app chauffeur)** | **L'ordre porte du sens : un pointage parti avant le démarrage n'a aucun trajet auquel se rattacher** |
| **Réconcilier plutôt que rejouer (`trajetDemarrer`)** | **MS1 refuse un second démarrage ; relire `mon-actif` et adopter le trajet existant évite une erreur permanente pour un effet déjà obtenu** |
| **Positions GPS jamais rejouées** | **`PositionRequest` n'a pas d'horodatage : un point rejoué deviendrait une fausse position courante** |
| **`ApiClient` injectable (≠ singleton `Api.instance`)** | **Sans cette couture les tests s'arrêtent au login — c'est ce qui limitait `parent-mobile` à 16 tests** |
| **Config centralisée (MS13) plutôt que `.env` par service** | **Les coordonnées de l'école vivaient à 6 endroits et MS4 en avait une version fausse de 900 m que rien ne pouvait révéler** |
| **Catalogue en code, valeurs en base** | **Ajouter un réglage = une ligne ; corriger un libellé = un redéploiement. Aucune migration, et `reset` sait toujours à quoi revenir** |
| **`/internal` non routée par la passerelle** | **Les clés API doivent sortir en clair pour MS9, mais jamais vers le web. La protection est le routage, pas un rôle** |
| **`.env` = amorçage, MS13 = surcharge** | **Une valeur vide côté MS13 signifie « non renseignée », pas « effacer » — sans cette règle, MS9 a réellement perdu ses clés API (piège n° 21b)** |
| **Le lot de paramètres est validé en bloc** | **Un jeu de seuils à moitié appliqué est pire qu'un enregistrement refusé** |
| **Une ligne de notification par ÉVÉNEMENT, pas par appareil** | **Un parent connecté sur trois origines aurait vu le même message en triple dans son application. On perd le diagnostic par appareil ; une table de livraison séparée serait la réponse en production** |
| **L'enregistrement d'un jeton FCM est idempotent** | **Un jeton est stable par installation : il revient à chaque connexion. Insérer au lieu de réaffecter violait la contrainte UNIQUE dès la 2ᵉ connexion du même appareil** |
| **Verrou d'entrée de zone plutôt que simple cooldown** | **Le métier veut « une annonce par arrivée », pas « une annonce toutes les N minutes ». Le verrou traite le cas dominant — le bus stationné à l'école qui continue d'émettre sa position** |
| **`push_service` injecté et qui ne lève jamais** | **Le push est un confort : Firebase absent, navigateur sans Push API ou MS4 injoignable ne doivent ni bloquer la connexion ni empêcher les tests de tourner sans réseau** |
| **Socle Flutter dupliqué (pas de package partagé)** | **`parent-mobile` est livrée et validée ; on ne la déstabilise pas avant la soutenance. Divergence gardée par les tests de parité `route_eta` copiés** |
