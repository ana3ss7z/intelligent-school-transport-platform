# Les notifications, expliquées simplement

> Document autonome sur **MS4 — NotificationService** et le canal de notifications poussées
> (Firebase Cloud Messaging). Se lit sans connaître le reste du projet.
>
> État au **25 août 2026**.

---

## 1. Le problème, en une phrase

La console d'administration affichait **10 157 notifications sur 10 157 en échec**. Toutes avec
le même motif : *« Aucun device FCM enregistré »*.

Ce n'était pas une panne. C'était le symptôme d'un canal qui n'avait **jamais été branché** — et
ce symptôme en cachait quatre autres, plus sérieux.

---

## 2. Ce qu'il faut comprendre d'abord : FCM n'est pas du SMS

C'est la source de confusion la plus fréquente sur ce sujet.

**Firebase Cloud Messaging n'a rien à voir avec un numéro de téléphone.** Il n'envoie pas de SMS.
Il pousse un message vers une **installation d'application** — une app installée sur un téléphone,
ou un site ouvert dans un profil de navigateur.

Chaque installation possède un **jeton** (*token*), une longue chaîne de caractères générée par
Firebase à l'intérieur de l'application. C'est ce jeton, et lui seul, qui permet d'atteindre
l'appareil.

Trois conséquences pratiques :

| | |
|---|---|
| **Le jeton identifie un appareil, pas une personne** | Si un parent se déconnecte et qu'un chauffeur se connecte sur le même navigateur, c'est **le même jeton**. |
| **Le jeton est stable** | Il ne change pas à chaque connexion. Il revient identique, jour après jour. |
| **Sans jeton enregistré, aucun push n'est possible** | Peu importe que Firebase soit parfaitement configuré côté serveur. |

---

## 3. Une notification voyage par deux chemins

C'est la clé pour comprendre pourquoi « 10 157 échecs » ne voulait **pas** dire « 10 157 messages
perdus ».

```
                    ┌──────────────────────────────────┐
   Un événement     │  MS4 enregistre la notification  │
   (enfant monté,   │       dans la base de données    │
    bus arrivé…)    └──────────────┬───────────────────┘
                                   │
                 ┌─────────────────┴─────────────────┐
                 │                                   │
        CHEMIN 1 — dans l'app             CHEMIN 2 — le push
                 │                                   │
   Le parent ouvre l'application        Le téléphone sonne, même
   et lit sa liste de notifications     application fermée
                 │                                   │
        ✅ marchait déjà                    ❌ jamais branché
```

**Le chemin 1 n'a jamais cessé de fonctionner.** La lecture (`GET /mes-notifications`) ne filtre
pas sur le statut d'envoi : le parent voyait donc bien toutes ses notifications dans
l'application. Le statut `ECHEC` signifiait seulement *« le téléphone n'a pas sonné »*.

C'est aussi pourquoi le défaut a pu passer inaperçu si longtemps : rien de visible ne manquait.

---

## 4. Les cinq défauts trouvés

### a) Aucun client n'enregistrait de jeton — *la cause racine*

L'endpoint `POST /api/notifications/device-token` existait depuis l'origine. **Personne ne
l'appelait**, sauf la console de test HTML. Aucune des applications Flutter ne déclarait de
dépendance Firebase.

En base : **2 jetons, 0 actif** — deux faux jetons de test, que Firebase avait rejetés et que MS4
avait automatiquement désactivés. *(Cette logique-là, au moins, fonctionnait.)*

Firebase côté serveur, lui, était correctement configuré depuis le début.

### b) Une rafale de notifications que rien ne freinait

**94 % des notifications** (9 546 sur 10 157) étaient du type « Le bus est arrivé à l'école ».

La règle notifiait tous les parents du bus **à chaque position GPS reçue** dans le rayon de
l'école. Or un bus stationné continue d'émettre sa position. Mesuré dans les données réelles :

- **150 notifications identiques par parent**, espacées de **1,2 seconde** ;
- un parent en cumulait **210** ;
- pic à **1 110 notifications pour un seul bus en une minute**.

> ⚠️ **C'est l'absence de jeton qui cachait ce défaut.** Le jour où l'on branche le push sans
> l'avoir corrigé, chaque famille reçoit **150 alertes en trois minutes**.

Le contraste est éclairant : la notification « le bus arrive dans ~N min », produite par MS12,
possède un anti-rebond depuis toujours — **maximum 4 par parent, à un jour d'écart**. Le motif
existait dans le projet ; MS4 ne l'appliquait simplement pas.

### c) Une ligne enregistrée par appareil, et non par événement

MS4 écrivait une ligne d'historique **à chaque envoi**, donc une par appareil.

Invisible tant qu'il n'y a aucun appareil (zéro appareil ⇒ exactement une ligne). Mais dès qu'un
parent est connecté sur la console web **et** l'application parent **et** son téléphone, le même
événement aurait produit **trois lignes** — et la famille aurait vu le message **en triple** dans
son application.

### d) Réenregistrer un jeton provoquait une erreur serveur

La colonne `fcm_token` porte une contrainte **UNIQUE**. Or l'enregistrement désactivait la ligne
existante *sans la supprimer*, puis en insérait une nouvelle avec le même jeton → violation de
contrainte, **HTTP 500**.

Comme un jeton est **stable par installation** (§2), cela signifie que **toute deuxième connexion
depuis le même appareil échouait**. Ce n'est pas un cas limite : c'est le cas normal.

### e) Le journal se téléchargeait en entier à chaque rafraîchissement

La page d'administration paginait à 25 lignes… **côté navigateur**. Le serveur, lui, renvoyait la
table complète — plus de 10 000 lignes — à chaque sondage automatique. Et cette table grossit de
plus de mille lignes par minute pendant une simulation.

---

## 5. Ce qui a été corrigé

### Le verrou d'entrée de zone

L'annonce se déclenche désormais au **franchissement** du rayon, pas tant que le bus y reste.

```
   Bus loin        Bus entre dans le rayon      Bus stationné       Bus repart
      │                     │                        │                  │
   verrou levé  ──▶   🔔 ANNONCE + verrou posé ──▶  silence  ──▶  verrou levé
                                                  (149 pings)      (au-delà de
                                                                   rayon × 1,5)
```

Trois protections superposées :

1. **le verrou** — une annonce par arrivée réelle ;
2. **la marge d'hystérésis** — le bus doit s'éloigner à `rayon × 1,5` (225 m par défaut) pour
   réarmer. Sans elle, un bruit GPS de ±20 m ferait clignoter l'alerte sur un bus immobile posé
   sur la frontière ;
3. **un délai minimal** réglable depuis la console (30 min par défaut, `0` pour le désactiver).

Un quatrième détail compte : au **démarrage d'un trajet**, le verrou est posé sans notifier. La
tournée part de l'école, donc le bus y est déjà — sans cela, le premier point GPS annoncerait une
« arrivée » au moment même du départ. Le cas se produit à chaque redémarrage de MS4.

### Une ligne par événement

L'écriture est sortie de la boucle d'envoi. Une ligne décrit désormais **l'événement métier**, et
non la tentative : statut *envoyé* dès qu'**au moins un** appareil a reçu.

Contrepartie assumée : on perd le détail par appareil (un échec partiel n'apparaît qu'au journal
technique). Un suivi fin exigerait une table de livraison séparée — écarté à ce stade du projet.

### Un enregistrement idempotent

La ligne existante est **réutilisée et réaffectée** au lieu d'être doublée. Le jeton appartient à
l'appareil : quand celui-ci change de main, il suit le nouvel utilisateur.

### Le rôle chauffeur

`POST` et `DELETE /device-token` sont ouverts à **CHAUFFEUR** en plus de PARENT. MS4 envoyait déjà
des notifications aux chauffeurs et leur ouvrait la lecture ; seul l'enregistrement restait
réservé aux parents, ce qui rendait leur push structurellement impossible.

### Le journal paginé côté serveur

`GET /api/notifications` accepte `page`, `size`, `tri`, `sens`, `adminSeulement` et renvoie une
enveloppe paginée. Le tri passe par une **liste blanche** de colonnes — sans quoi un nom de
colonne inventé produirait une erreur 500.

Corollaire : la console ne voyant plus qu'une tranche, elle ne peut plus compter les alertes admin
en filtrant sa liste. Ce total vient maintenant du serveur.

---

## 6. Le cycle de vie d'un jeton

```
  Connexion  ──▶  demande d'autorisation  ──▶  Firebase renvoie le jeton
                                                        │
                                                        ▼
                                        POST /device-token  (idempotent)
                                                        │
                          ┌─────────────────────────────┼──────────────────────────┐
                          ▼                             ▼                          ▼
                 le jeton tourne              un autre se connecte           Déconnexion
                 (onTokenRefresh)             sur le même appareil                 │
                          │                             │                          ▼
                    réenregistré              la ligne est réaffectée     DELETE /device-token
                                                                          (avant d'effacer le JWT)
```

Deux règles à ne pas oublier :

- **L'enregistrement est rejoué à chaque connexion.** C'est ce qui réaffecte le jeton au bon
  compte lorsque l'appareil change de main.
- **Le détachement part avant l'effacement du jeton de session**, car l'appel est authentifié.

---

## 7. Configuration Firebase

Projet : **`transport-scolaire-meknes`** — il **existe déjà**, MS4 s'y authentifie.

> 🚫 **Ne jamais en recréer un.** Les identifiants Firebase sont uniques au monde : un projet
> recréé sous le même nom porterait un identifiant différent. Les jetons s'enregistreraient
> normalement, mais **tous les envois échoueraient** en `SENDER_ID_MISMATCH`.

### Trois applications, trois origines

| Application Firebase | Sert | Origine |
|---|---|---|
| `Transport Web` | console web — **admin, parent et chauffeur** | `localhost:5173` |
| parent-mobile | app parent Flutter | `localhost:5174` + APK Android |
| chauffeur-mobile | app chauffeur Flutter | `localhost:5175` + APK Android |

La console web sert les **trois rôles depuis une seule origine**. Or un jeton web est lié au
couple *origine + service worker* : une seule application Firebase suffit donc pour les trois
espaces, et tous partagent le même jeton.

### Ce qu'il faut sur le web, et pas sur Android

| | Web | Android |
|---|---|---|
| **Clé VAPID** — passée à `getToken()` | obligatoire | inutile |
| **Service worker** `firebase-messaging-sw.js` | obligatoire | inutile |
| `google-services.json` | inutile | obligatoire |

Ce sont les deux oublis classiques, et ils échouent **silencieusement** : sans clé VAPID,
`getToken()` renvoie `null` ; sans service worker, le jeton est obtenu mais **aucun message
n'arrive**.

> **Ni la clé VAPID ni `google-services.json` ne sont des secrets.** La première est une clé
> *publique*, le second est extractible de n'importe quel APK. Ils vivent dans les fichiers de
> configuration. Seul `firebase-service-account.json` (côté serveur) est réellement sensible.
>
> **Aucune empreinte SHA-1 n'est requise** pour FCM — elle sert à Google Sign-In, aux Dynamic
> Links et à l'authentification par téléphone. C'est le principal gouffre de temps sur cette
> configuration.

---

## 8. Vérifier que ça marche

```sql
-- 1. Un jeton est enregistré après connexion
SELECT parent_id, plateforme, actif FROM device_tokens;
--    attendu : une ligne WEB (ou ANDROID), actif = true

-- 2. Un événement produit UNE ligne, pas une par appareil
SELECT count(*) FROM notifications WHERE source_id = ? AND type = ?;
--    attendu : 1, statut_envoi = 'ENVOYE'
```

Le test de bout en bout qui compte :

1. se connecter en PARENT sur `:5174`, avec un **profil de navigateur persistant** ;
2. déclencher un pointage depuis `html_tests/simulation-control.html` ;
3. la notification s'affiche dans le navigateur **et** la ligne est en `ENVOYE` ;
4. se connecter **aussi** sur `:5173` avec le même compte et redéclencher :
   **2 envois, 1 seule ligne**, aucun doublon dans l'application ;
5. faire entrer un bus dans le rayon de l'école et l'y laisser stationner :
   **une seule** notification.

---

## 9. Pièges à connaître

**`flutter run -d chrome` repart d'un profil de navigateur vierge à chaque lancement.**
L'autorisation de notification et le jeton sont donc réinitialisés à chaque exécution, et les
jetons morts s'accumulent en base. Les lanceurs VS Code passent désormais
`--web-browser-flag=--user-data-dir=…` pour fixer un profil persistant.

**Le push web ne réveille pas un navigateur éteint.** Sur ordinateur, si le navigateur est
entièrement fermé, rien n'arrive. C'est la différence de fond avec l'application Android
installée, où Firebase réveille l'application.

**`firebase_core` applique l'ancien plugin Kotlin (KGP).** L'APK se construit aujourd'hui sur la
chaîne AGP 9.0.1 / Gradle 9.1 / Kotlin 2.3.20, mais Flutter émet un avertissement explicite :
*« Future versions of Flutter will fail to build »*. Même famille de piège que l'épinglage de
`path_provider_android` pour éviter `jni`. À surveiller à chaque montée de version.

**iOS est hors périmètre** — il exige des certificats APNs et un compte Apple payant.

---

## 10. En résumé

| | Avant | Après |
|---|---|---|
| Jetons enregistrés | 0 | un par appareil connecté |
| Notifications en échec | 100 % | uniquement les vraies erreurs |
| « Bus arrivé » par arrivée | jusqu'à 150 par parent | **1** |
| Lignes par événement | une par appareil | **1** |
| Deuxième connexion d'un appareil | **HTTP 500** | fonctionne |
| Chargement du journal | table entière à chaque sondage | une page |
| Push chauffeur | impossible | possible |

**Vérifications** — MS4 : `mvn test` **17/17**. `parent-mobile` : `flutter analyze` **0 issue**,
`flutter test` **38/38**, `build web` ✅, `build apk` ✅ (53,4 Mo).

---

## 11. Ce qu'il reste à faire

- Brancher le push sur **`web-admin`** (console React) et **`chauffeur-mobile`**.
- Vérifier l'émission sur un **téléphone Android physique**.
- Décider du sort des **10 157 lignes de simulation** encore en base : elles faussent le compteur
  « Échecs » de la console tant qu'elles n'ont pas été archivées.

---

## Voir aussi

- [`GUIDE_PARAMETRES.md`](GUIDE_PARAMETRES.md) — les réglages de notification depuis la page
  **Réglages** (section 7).
- `CLAUDE.md` — architecture d'ensemble et journal des décisions.
