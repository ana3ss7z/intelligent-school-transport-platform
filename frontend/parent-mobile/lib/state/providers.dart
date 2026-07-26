import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api.dart';
import '../models/models.dart';
import '../services/auth_store.dart';
import '../services/gps_socket.dart';

final authStoreProvider = Provider<AuthStore>((ref) => AuthStore());

/// Utilisateur chargé au démarrage (surchargé dans main() après lecture du storage).
final initialUserProvider = Provider<AuthUser?>((ref) => null);

/// Session courante. `null` = déconnecté → écran de login.
class AuthController extends Notifier<AuthUser?> {
  @override
  AuthUser? build() {
    final initial = ref.read(initialUserProvider);
    if (initial != null) Api.instance.token = initial.token;
    // Expiration de session (401) → déconnexion automatique.
    Api.instance.onUnauthorized = () {
      if (state != null) logout();
    };
    return initial;
  }

  Future<void> login(String email, String motDePasse) async {
    final user = await Api.instance.login(email, motDePasse);
    Api.instance.token = user.token;
    await ref.read(authStoreProvider).save(user);
    state = user;
  }

  Future<void> logout() async {
    Api.instance.token = null;
    await ref.read(authStoreProvider).clear();
    state = null;
  }
}

final authProvider = NotifierProvider<AuthController, AuthUser?>(AuthController.new);

/// Données « mes enfants » partagées par l'accueil et la carte.
class ChildrenData {
  final List<Eleve> enfants;
  final Map<int, Bus> busById;
  final List<int> busIds; // bus distincts des enfants
  final List<Bus> mesBus;

  ChildrenData({
    required this.enfants,
    required this.busById,
    required this.busIds,
    required this.mesBus,
  });

  static ChildrenData empty() =>
      ChildrenData(enfants: const [], busById: const {}, busIds: const [], mesBus: const []);
}

final childrenProvider = FutureProvider.autoDispose<ChildrenData>((ref) async {
  final user = ref.watch(authProvider);
  if (user == null) return ChildrenData.empty();

  final results = await Future.wait([
    Api.instance.getMesEnfants(user.userId),
    Api.instance.getBus(),
  ]);
  final enfants = results[0] as List<Eleve>;
  final buses = results[1] as List<Bus>;
  final busById = {for (final b in buses) b.id: b};
  final busIds = enfants.map((e) => e.busId).whereType<int>().toSet().toList();
  final mesBus = busIds.map((id) => busById[id]).whereType<Bus>().toList();
  return ChildrenData(enfants: enfants, busById: busById, busIds: busIds, mesBus: mesBus);
});

/// WebSocket GPS partagé (une seule connexion tant que le shell est monté).
final gpsSocketProvider = Provider.autoDispose<GpsSocket>((ref) {
  final socket = GpsSocket();
  ref.onDispose(socket.dispose);
  return socket;
});
