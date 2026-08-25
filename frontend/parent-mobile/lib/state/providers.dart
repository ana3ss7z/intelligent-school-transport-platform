import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api.dart';
import '../config/env.dart';
import '../services/params_service.dart';
import '../models/models.dart';
import '../services/auth_store.dart';
import '../services/gps_socket.dart';
import '../services/push_service.dart';

final authStoreProvider = Provider<AuthStore>((ref) => AuthStore());

/// Notifications poussées. Les appels réseau sont injectés plutôt que pris sur
/// `Api.instance`, pour que les tests puissent observer l'enregistrement sans Firebase.
final pushServiceProvider = Provider<PushService>((ref) {
  return PushService(
    enregistrer: (token, plateforme) =>
        Api.instance.enregistrerDeviceToken(token, plateforme),
    supprimer: (token) => Api.instance.supprimerDeviceToken(token),
  );
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
    // La lecture des paramètres exige un jeton : au premier lancement, c'est ici — et
    // seulement ici — que MS13 devient interrogeable. Sans await : un service de
    // configuration lent ou absent ne doit pas retarder l'entrée dans l'application.
    unawaited(ref.read(paramsServiceProvider).charger());
    // Même motif, et pour la même raison : demander l'autorisation puis joindre Firebase et
    // MS4 peut prendre plusieurs secondes. Rejoué à chaque connexion — c'est ce qui réaffecte
    // le jeton au bon compte quand l'appareil change de main.
    unawaited(ref.read(pushServiceProvider).activer());
  }

  Future<void> logout() async {
    // Avant d'effacer le jeton de session : l'appel de détachement est authentifié.
    await ref.read(pushServiceProvider).desactiver();
    Api.instance.token = null;
    await ref.read(authStoreProvider).clear();
    state = null;
  }
}

final authProvider = NotifierProvider<AuthController, AuthUser?>(
  AuthController.new,
);

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

  static ChildrenData empty() => ChildrenData(
    enfants: const [],
    busById: const {},
    busIds: const [],
    mesBus: const [],
  );
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
  return ChildrenData(
    enfants: enfants,
    busById: busById,
    busIds: busIds,
    mesBus: mesBus,
  );
});

/// WebSocket GPS partagé (une seule connexion tant que le shell est monté).
final gpsSocketProvider = Provider.autoDispose<GpsSocket>((ref) {
  final socket = GpsSocket();
  ref.onDispose(socket.dispose);
  return socket;
});

/// Paramètres applicatifs (MS13) : coordonnées de l'école, intervalles de sondage.
///
/// Lit `/api/parametres` avec un Dio dédié plutôt qu'en ajoutant une méthode à [Api] :
/// l'application est livrée et couverte par ses tests, on ne touche pas à son client réseau
/// pour un besoin de configuration.
final paramsServiceProvider = Provider<ParamsService>((ref) {
  return ParamsService(() async {
    final token = ref.read(authProvider)?.token;
    if (token == null) return const <dynamic>[];
    final dio = Dio(BaseOptions(
      baseUrl: Env.gateway,
      connectTimeout: Env.httpTimeout,
      receiveTimeout: Env.httpTimeout,
      headers: {'Authorization': 'Bearer $token'},
    ));
    final r = await dio.get<dynamic>('/api/parametres');
    return r.data is List ? r.data as List<dynamic> : const <dynamic>[];
  });
});
