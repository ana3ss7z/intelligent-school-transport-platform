# Configuration par cible

Un fichier JSON par environnement, injecté au lancement via `--dart-define-from-file`.
**Le code Dart n'est jamais à modifier** — `lib/config/env.dart` lit ces valeurs via
`String.fromEnvironment`.

| Fichier | Cible | Backend visé |
|---|---|---|
| `env.chrome.json` | Navigateur (dev sur le PC) | `localhost` |
| `env.phone.json` | Téléphone physique / émulateur | IP LAN du PC |

## Lancement

```bash
# Chrome (format téléphone via DevTools Ctrl+Shift+M)
flutter run -d chrome --web-port 5174 --dart-define-from-file=config/env.chrome.json

# Téléphone physique (ADB sans fil ou USB)
flutter run --dart-define-from-file=config/env.phone.json
```

Ou en **un clic** depuis VS Code : menu *Run and Debug* → « Parent App — Chrome » ou
« Parent App — Téléphone » (voir `.vscode/launch.json` à la racine du dépôt).

## Si l'IP du PC change

L'IP LAN peut changer au redémarrage du routeur. Dans ce cas, **seul `env.phone.json` est à éditer** :

```bash
ipconfig   # relever l'IPv4 de l'adaptateur « Wi-Fi »
```

Prérequis côté PC pour la cible téléphone :
- backend démarré et à l'écoute (Gateway `8080`, WebSocket GPS `8083`) ;
- pare-feu Windows ouvert sur ces deux ports ;
- téléphone et PC sur le **même réseau Wi-Fi**.
