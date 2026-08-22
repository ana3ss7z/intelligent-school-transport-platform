import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/dio_api.dart';
import '../models/models.dart';
import '../services/auth_store.dart';
import '../services/gps_emitter.dart';
import '../services/gps_socket.dart';
import '../services/outbox.dart';
import '../services/outbox_sync.dart';
import '../services/tournee_cache.dart';

/// Client réseau. **Toujours** lu via ce provider, jamais via un singleton :
/// c'est la couture qui rend les écrans testables (les tests le surchargent
/// avec un faux client).
final apiProvider = Provider<ApiClient>((ref) => DioApi());

final authStoreProvider = Provider<AuthStore>((ref) => AuthStore());

final tourneeCacheProvider = Provider<TourneeCache>((ref) => TourneeCache());

/// File d'écritures différées, partagée par tous les écrans.
final outboxProvider = Provider<Outbox>((ref) {
  final outbox = Outbox(ref.read(apiProvider));
  ref.onDispose(outbox.dispose);
  return outbox;
});

/// Déclencheurs de vidange de la file (connectivité, reprise d'app, balayage).
///
/// Passe par un provider pour que les tests de widgets puissent le neutraliser :
/// `connectivity_plus` n'a pas d'implémentation dans l'environnement de test, et
/// surtout cela permet de **vérifier que le shell le démarre bien** — s'il ne le
/// démarrait pas, la file ne se viderait jamais et rien ne le signalerait.
final outboxSyncProvider = Provider<OutboxSync>((ref) {
  final sync = OutboxSync(ref.read(outboxProvider));
  ref.onDispose(sync.dispose);
  return sync;
});

final gpsEmitterProvider = Provider<GpsEmitter>((ref) {
  final emitter = GpsEmitter(ref.read(apiProvider));
  ref.onDispose(emitter.dispose);
  return emitter;
});

/// Mode de thème (système par défaut, bascule clair/sombre).
class ThemeModeController extends Notifier<ThemeMode> {
  @override
  ThemeMode build() => ThemeMode.system;

  void toggle(Brightness current) {
    state = current == Brightness.dark ? ThemeMode.light : ThemeMode.dark;
  }
}

final themeModeProvider = NotifierProvider<ThemeModeController, ThemeMode>(
  ThemeModeController.new,
);

/// Utilisateur chargé au démarrage (surchargé dans main() après lecture du storage).
final initialUserProvider = Provider<AuthUser?>((ref) => null);

/// Session courante. `null` = déconnecté → écran de login.
class AuthController extends Notifier<AuthUser?> {
  @override
  AuthUser? build() {
    final api = ref.read(apiProvider);
    final initial = ref.read(initialUserProvider);
    if (initial != null) api.token = initial.token;
    // Expiration de session (401) → déconnexion automatique.
    api.onUnauthorized = () {
      if (state != null) logout();
    };
    return initial;
  }

  Future<void> login(String email, String motDePasse) async {
    final api = ref.read(apiProvider);
    final user = await api.login(email, motDePasse);
    api.token = user.token;
    await ref.read(authStoreProvider).save(user);
    state = user;
  }

  Future<void> logout() async {
    ref.read(apiProvider).token = null;
    await ref.read(authStoreProvider).clear();
    state = null;
  }
}

final authProvider = NotifierProvider<AuthController, AuthUser?>(
  AuthController.new,
);

/// Le bus affecté au chauffeur connecté, résolu depuis la flotte.
///
/// MS1 n'expose pas de route « mon bus » : la console web fait le même filtrage
/// côté client (`buses.find(b => b.chauffeurId === user.userId)`).
final myBusProvider = FutureProvider<Bus?>((ref) async {
  final user = ref.watch(authProvider);
  if (user == null) return null;
  final buses = await ref.read(apiProvider).getBus();
  for (final b in buses) {
    if (b.chauffeurId == user.userId) return b;
  }
  return null;
});

/// WebSocket GPS partagé (une seule connexion tant que le shell est monté).
final gpsSocketProvider = Provider.autoDispose<GpsSocket>((ref) {
  final socket = GpsSocket();
  ref.onDispose(socket.dispose);
  return socket;
});
