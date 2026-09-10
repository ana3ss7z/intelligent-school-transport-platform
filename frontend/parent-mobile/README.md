# 📱 App mobile PARENT — Transport Scolaire Intelligent

Application **Flutter 3.44 / Dart 3.12** de l'espace parent : 6 écrans miroir de la console web
([`web-app/src/pages/Parent*.tsx`](../web-app/src/pages/)), consommant le **même backend**
(Gateway `:8080` + WebSocket GPS `:8083`). **Aucun delta backend** — les endpoints étaient déjà ouverts au rôle
`PARENT`.

Cible de développement **Chrome `:5174`**, code **Android-ready**.

> Application **en lecture seule** : le parent consulte, il n'écrit rien. C'est ce qui la distingue de
> [`../chauffeur-mobile/`](../chauffeur-mobile/), où chaque action est une écriture à réconcilier.

---

## Écrans

| Écran | Contenu |
|-------|---------|
| **Login** | JWT (`flutter_secure_storage`), 401 → déconnexion automatique, garde de rôle `PARENT` |
| **Mon espace** | Enfants · présence · bus + **compte à rebours** « le bus arrive dans ~N min », **uniquement si un trajet est démarré** |
| **Carte de mon enfant** | `flutter_map` (OSM/CARTO), bus filtrés aux enfants, **glisse interpolée** entre pings GPS, tuiles sombres |
| **Prévisions ETA** | Sens matin/soir + heure de départ → heure de passage estimée **par enfant**, rang dans la tournée |
| **Messagerie** | Réception des diffusions du chauffeur (poll 15 s) |
| **Notifications** | Historique personnel (poll 15 s) |
| **Assistant** | Chat MS9 (`POST /api/llm/chat`) — FR / arabe / darija |

### La portée est imposée par le jeton, pas par la requête

`POST /api/planification/mes-enfants` planifie la tournée **entière** (indispensable au cumul depuis l'école)
mais ne renvoie que les étapes des enfants du demandeur, `parentId` étant lu dans le JWT. Les routes
`/tournee` et `/tournees` restent **interdites au rôle PARENT** : une tournée complète contient l'adresse de
toutes les familles du bus.

---

## ETA — pourquoi ce n'est pas une distance à vol d'oiseau

La tournée boucle `école → élèves → école`. Pendant le ramassage, le bus **s'éloigne** de l'école : un ETA
point-à-point *augmente* alors que le bus avance normalement. `lib/services/route_eta.dart` projette la position
sur la polyligne figée du trajet et mesure la **distance restante sur le circuit**.

**Règle de destination** : pas encore à bord → *chez vous* · à bord le matin → *l'école* · le soir → *chez vous*.

Deux subtilités, mesurées sur une vraie tournée de 753 points :

- **Le circuit est un cycle fermé** — premier et dernier point à **0,0 m**. Sans mémoire de progression, le bus
  arrivé se recale sur le *départ* : à 99 % du parcours, le compte à rebours passait de 1,1 min à **35,4 min**,
  pile au moment où le parent le regarde. D'où `depuisAlongM`, l'abscisse déjà atteinte, réinjectée d'un calcul
  au suivant. Elle est mémorisée **par bus** (deux enfants d'une même famille peuvent le partager) et purgée au
  seul changement de polyligne — surtout pas quand un enfant monte.
- **La vitesse vient de la polyligne mesurée**, pas du total annoncé par MS5.

> Ce fichier est le **jumeau byte-identique** de `chauffeur-mobile/lib/services/route_eta.dart`, et l'équivalent
> de `web-app/src/lib/routeEta.ts`. Les tests de parité et la fixture d'une tournée réelle
> (`test/fixtures/tournee_groupe1.json`) existent des deux côtés : une divergence casse les deux suites.

---

## Architecture

```
lib/
├── api/api.dart          client Dio (Bearer, 401→logout, timeouts 20 s / 120 s pour ETA + LLM)
├── config/env.dart       URLs injectées à la compilation (--dart-define-from-file)
├── models/models.dart    DTO backend (camelCase Java / snake_case Python)
├── services/             auth_store · gps_socket (auto-reconnect 2,5 s, throttle 1 s) · route_eta
├── state/providers.dart  Riverpod : auth, enfants, socket GPS partagés
├── screens/              shell (6 onglets) + écrans
└── widgets/common.dart   skeletons shimmer, états vides, chips
```

**UI/UX & perf** : Material 3 **clair + sombre** avec bascule, tokens 4/8 pt, skeletons shimmer, compte à rebours
animé, `RepaintBoundary` sur la carte, `const`, `ListView.builder` + clés, `Semantics` sur les tuiles, cartes
enfants et pastilles.

---

## Lancement

```bash
flutter pub get

# Navigateur (backend sur localhost)
flutter run -d chrome --web-port 5174 --dart-define-from-file=config/env.chrome.json

# Téléphone physique (backend sur l'IP LAN du PC, pare-feu 8080/8083 ouvert)
flutter run --dart-define-from-file=config/env.phone.json
```

Ou **en un clic** depuis VS Code : « Parent App — Chrome » / « — Téléphone » (`.vscode/launch.json`, racine du
dépôt). Configuration détaillée : [`config/README.md`](config/README.md).

---

## Qualité

```bash
flutter analyze     # 0 issue
flutter test        # 25/25
flutter build web --release
flutter build apk --release   # 51,5 Mo
```

⚠️ **`dependency_overrides: path_provider_android: 2.2.17` est obligatoire.** Les versions ≥ 2.3 tirent le paquet
`jni`, dont le `build.gradle` appelle l'ancienne méthode Groovy `kotlin()` — incompatible avec AGP 9 / Gradle 9
utilisés ici (`assembleRelease` échoue sur *« Could not find method kotlin() on project ':jni' »*). À retirer
quand `jni` sera compatible. Sans effet sur la cible web.
