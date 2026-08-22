import 'package:chauffeur_app/models/models.dart';
import 'package:chauffeur_app/services/auth_store.dart';
import 'package:chauffeur_app/services/gps_emitter.dart';
import 'package:chauffeur_app/services/gps_socket.dart';
import 'package:chauffeur_app/services/outbox.dart';
import 'package:chauffeur_app/services/outbox_sync.dart';
import 'package:chauffeur_app/state/providers.dart';
import 'package:chauffeur_app/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_api.dart';

/// Monte un écran dans un arbre complet, avec toutes les dépendances simulées.
///
/// Deux pièges évités ici :
///  · `GpsSocket` ouvrirait une vraie WebSocket vers MS3 et laisserait un timer
///    de reconnexion derrière lui → `autoConnect: false` ;
///  · `Outbox` écrirait dans `shared_preferences` (plugin absent en test) →
///    [MemoryOutboxStore] ; idem pour `flutter_secure_storage` → [FakeAuthStore].
Widget monterEcran(
  Widget ecran, {
  required FakeApi api,
  Outbox? outbox,
  AuthUser? utilisateur,
  Brightness brightness = Brightness.light,
  FakeOutboxSync? sync,

  /// false pour les écrans qui apportent déjà leur propre `Scaffold`
  /// (login, notifications, historique, ETA) — un Scaffold imbriqué fausse la
  /// hauteur disponible et pousse des boutons hors du viewport de test.
  bool avecScaffold = true,
}) {
  return ProviderScope(
    overrides: [
      apiProvider.overrideWithValue(api),
      authStoreProvider.overrideWithValue(FakeAuthStore()),
      initialUserProvider.overrideWithValue(utilisateur ?? FakeApi.utilisateur),
      outboxProvider.overrideWith(
        (ref) => outbox ?? Outbox(api, store: MemoryOutboxStore()),
      ),
      gpsSocketProvider.overrideWith((ref) => GpsSocket(autoConnect: false)),
      outboxSyncProvider.overrideWith(
        (ref) => sync ?? FakeOutboxSync(outbox ?? Outbox(api)),
      ),
      // L'émetteur reste inerte : `enabled` est false par défaut, donc `bind()`
      // ne touche jamais au plugin de géolocalisation.
      gpsEmitterProvider.overrideWith((ref) => GpsEmitter(api)),
    ],
    child: MaterialApp(
      theme: buildTheme(brightness),
      home: avecScaffold ? Scaffold(body: ecran) : ecran,
    ),
  );
}

/// Agrandit le viewport de test.
///
/// Par défaut il fait 800x600 : un `ListView` n'inflate que les éléments
/// visibles, donc les élèves du bas de la tournée n'existent même pas dans
/// l'arbre et `find.text` ne les voit pas. On teste l'écran, pas le défilement.
void grandEcran(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 3000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

/// Neutralise les déclencheurs réseau (`connectivity_plus` n'existe pas en test)
/// tout en enregistrant que le shell a bien démarré la vidange de la file.
class FakeOutboxSync extends OutboxSync {
  FakeOutboxSync(super.outbox);
  bool demarre = false;

  @override
  void start() => demarre = true;

  @override
  void dispose() {}
}

/// Session en mémoire — `flutter_secure_storage` n'a pas d'implémentation dans
/// l'environnement de test.
class FakeAuthStore implements AuthStore {
  AuthUser? utilisateur;

  @override
  Future<AuthUser?> load() async => utilisateur;

  @override
  Future<void> save(AuthUser user) async => utilisateur = user;

  @override
  Future<void> clear() async => utilisateur = null;
}
