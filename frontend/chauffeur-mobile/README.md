# 🚐 App mobile CHAUFFEUR — Transport Scolaire Intelligent

Application **Flutter** de l'espace chauffeur : 7 écrans miroir de la console web
([`web-admin/src/pages/Chauffeur*.tsx`](../web-admin/src/pages/)), consommant le **même backend**
(Gateway `:8080` + WebSocket GPS `:8083`). **Aucun delta backend.**

Cible de développement **Chrome `:5175`**, code **Android-ready**.

---

## Ce qui la distingue de l'app parent

L'app parent est **en lecture seule**. Ici, le chauffeur **écrit** — et le téléphone devient la **source GPS du
bus**. Trois conséquences structurent tout le code :

1. **Chaque action est optimiste** : l'interface bouge avant la réponse serveur, avec rollback si le serveur
   refuse et mise en file si le réseau manque.
2. **Le réseau est instable par nature** — un chauffeur roule. D'où une file d'écritures persistée.
3. **L'ordre des écritures porte du sens** : un pointage envoyé avant le démarrage du trajet n'a aucun trajet
   auquel se rattacher.

---

## Écrans

Barre basse à 5 destinations (Material 3 en plafonne le nombre) + une feuille « Plus » pour les écrans qu'on
consulte à l'arrêt, pas au volant.

| Écran | Contenu |
|-------|---------|
| **Ma tournée** | Cycle de vie du **Trajet** (démarrer/terminer), **pointage** montée/dépose, arrêt courant surligné + distance, KPI **« Fin de tournée »**, interrupteur d'émission GPS, signalement rapide |
| **Ma carte** | Position live de **son** bus (glisse interpolée entre pings), tracé de la tournée, arrêts numérotés — verts une fois traités —, suivi automatique débrayable |
| **Messagerie** | **Bidirectionnelle** avec l'administration + **diffusion aux parents** du groupe. Les deux canaux sont **volontairement étanches** : un « léger retard » destiné aux familles ne doit jamais partir à l'administration |
| **Mes incidents** | Incidents de son bus (poll 15 s) + formulaire (6 types, position jointe automatiquement) |
| *Plus →* **Prévisions ETA** | Heure de passage estimée à chaque arrêt |
| *Plus →* **Mes notifications** | Incident résolu sur son bus, messages, cycle de ses trajets |
| *Plus →* **Mes trajets** | Historique des tournées terminées |

---

## Le téléphone comme source GPS

`POST /api/gps/position` était **déjà ouvert au rôle CHAUFFEUR** côté MS3 — d'où l'absence de delta backend.

- Interrupteur **« Transmettre ma position », désactivé par défaut** : sinon le téléphone et `bus_simulator.py`
  se disputent le même bus. Pour une démo au simulateur, le laisser OFF.
- Émission **uniquement pendant un trajet**, 1 envoi / 5 s, filtre de déplacement 15 m.
- Écran verrouillé : le `ForegroundNotificationConfig` de `geolocator` tient un service de premier plan lié au
  flux de positions. On évite ainsi **`ACCESS_BACKGROUND_LOCATION`** (justification Play Store + second écran de
  consentement Android 11+) **et** un second isolate qui aurait imposé d'y recréer Dio et le JWT.

> ⚠️ **Conversion m/s → km/h obligatoire.** `geolocator` renvoie des m/s ; `bus_simulator.py` publie des km/h
> (40 en régime normal, 110 pour déclencher l'anomalie) et le seuil MS11 vaut **90 km/h**. Sans le ×3,6, la
> vitesse serait 3,6× trop faible et `VITESSE_EXCESSIVE` ne partirait **jamais** d'un vrai téléphone.

---

## File d'écritures hors ligne

`lib/services/outbox.dart` — **FIFO stricte, single-flight**, persistée en JSON dans `shared_preferences`, donc
survivant à la fermeture de l'app. Déclencheurs de vidange : retour de connectivité, reprise au premier plan, et
un balayage périodique (filet de sécurité : `connectivity_plus` signale qu'une interface est *montée*, pas
qu'internet est *joignable*).

La sémantique dépend du type d'écriture :

| Écriture | Idempotente ? | Traitement au rejeu |
|---|---|---|
| `presence` | ✅ valeur absolue (`?present=true\|false`) | Deux pointages du même élève sont **fusionnés** — une hésitation n'envoie qu'un appel |
| `trajetDemarrer` | ❌ MS1 renvoie `400 « Un trajet est déjà en cours »` | **Réconciliation, pas retry aveugle** : on relit `GET /api/trajets/mon-actif` et on **adopte** le trajet existant |
| `trajetTerminer` | ~ | Idem : plus de trajet actif ⇒ déjà clos |
| `incident` · `message` · `diffusion` | ❌ aucune clé d'idempotence côté serveur | **At-least-once assumé** : un doublon reste possible si la réponse se perd après commit. Plafond de **3 essais**, puis l'item est « parké » et la décision revient au chauffeur |

**Les positions GPS ne sont jamais rejouées.** `PositionRequest` n'a pas de champ horodatage (MS3 date à la
réception) : réémettre un point vieux de trois minutes écrirait une **fausse position courante**, bien pire qu'un
trou dans la trace.

### Démarrer hors ligne : refusé sans itinéraire en cache

MS1 accepte un trajet sans `geometrie` (le champ est optionnel), mais MS11 se retrouve alors **sans route de
référence** : `DEVIATION_ITINERAIRE` ne peut plus se déclencher, **silencieusement**. L'app met donc la tournée
en cache (`tournee_cache.dart`, clé `(groupeId, sens)`) et **refuse le démarrage** si elle n'a rien à envoyer,
plutôt que de partir à l'aveugle.

---

## ETA — pourquoi ce n'est pas une distance à vol d'oiseau

La tournée boucle `école → élèves → école`. Pendant le ramassage, le bus **s'éloigne** de l'école : un ETA
point-à-point *augmente* alors que le bus avance normalement. `lib/services/route_eta.dart` projette donc la
position sur la polyligne figée et mesure la **distance restante sur le circuit**.

Deux subtilités, mesurées sur une vraie tournée de 753 points :

- **Le circuit est un cycle fermé** — premier et dernier point à **0,0 m**. Sans mémoire de progression, le bus
  arrivé se recale sur le *départ* : à 99 % du parcours, l'ETA passait de 1,1 min à **35,4 min**. D'où le
  paramètre `depuisAlongM`, l'abscisse déjà atteinte, réinjectée d'un calcul au suivant.
- **La vitesse vient de la polyligne mesurée**, pas du total annoncé : au départ, l'ETA vaut alors exactement la
  durée annoncée par MS5.

> Ce fichier est le **jumeau** de `parent-mobile/lib/services/route_eta.dart` (byte-identique) et de
> `web-admin/src/lib/routeEta.ts`. Les tests de parité et la fixture réelle sont copiés dans les deux apps Dart :
> une divergence casse les tests des deux côtés.

---

## Architecture

```
lib/
├── api/          api_client.dart (interface) · dio_api.dart (implémentation Dio)
├── models/       DTO backend (camelCase Java / snake_case Python)
├── services/     outbox · outbox_sync · gps_emitter · gps_socket · tournee_cache · route_eta · geo
├── state/        providers Riverpod (api, auth, outbox, gpsEmitter, myBus…)
├── screens/      shell + 8 écrans
└── widgets/      common (skeletons, états vides) · outbox_banner
```

**Testabilité** — l'app parent expose un singleton `Api.instance`, ce qui borne ses tests au login. Ici, tout
passe par l'interface **`ApiClient`** derrière `apiProvider`, et `Outbox` derrière `outboxProvider` : les écrans
à actions sont testables, **y compris leurs chemins d'échec** — ceux qu'on ne verra jamais en démo.

---

## Lancement

```bash
flutter pub get

# Navigateur (backend sur localhost)
flutter run -d chrome --web-port 5175 --dart-define-from-file=config/env.chrome.json

# Téléphone physique (backend sur l'IP LAN du PC, pare-feu 8080/8083 ouvert)
flutter run --dart-define-from-file=config/env.phone.json
```

Ou **en un clic** depuis VS Code : « Chauffeur App — Chrome » / « — Téléphone » (`.vscode/launch.json`, racine du
dépôt). Configuration détaillée : [`config/README.md`](config/README.md).

---

## Qualité

```bash
flutter analyze     # 0 issue
flutter test        # 84/84
flutter build web --release
flutter build apk --release   # 54,3 Mo
```

⚠️ **`dependency_overrides: path_provider_android: 2.2.17` est obligatoire.** Les versions ≥ 2.3 tirent le paquet
`jni`, dont le `build.gradle` appelle l'ancienne méthode Groovy `kotlin()` — incompatible avec AGP 9 / Gradle 9
utilisés ici (`assembleRelease` échoue sur *« Could not find method kotlin() on project ':jni' »*). À retirer
quand `jni` sera compatible. Sans effet sur la cible web.
