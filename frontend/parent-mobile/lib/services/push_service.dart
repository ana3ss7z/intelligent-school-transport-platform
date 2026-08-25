import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import '../config/env.dart';

/// Notifications poussées (Firebase Cloud Messaging).
/// ==================================================
///
/// Le canal push existait côté serveur depuis l'origine mais n'a **jamais** été raccordé :
/// aucun client n'appelait `POST /api/notifications/device-token`. Résultat mesuré sur
/// l'export du 24/08 — **10 157 notifications sur 10 157 en ECHEC**, motif « Aucun device FCM
/// enregistré ». Les notifications restaient visibles dans l'application (le chemin de lecture
/// ignore le statut d'envoi), mais aucun téléphone ne sonnait.
///
/// Ce que FCM identifie
/// --------------------
/// Ni un compte, ni un numéro de téléphone : une **installation**. Sur le web, le jeton est lié
/// au couple *origine + service worker*, donc à un profil de navigateur. Deux conséquences que
/// le code doit assumer :
///
/// * le même jeton revient à **chaque** connexion depuis le même appareil — l'enregistrement
///   doit donc être idempotent (MS4 réaffecte la ligne existante au lieu d'insérer) ;
/// * un autre utilisateur qui se connecte depuis le même navigateur **hérite du même jeton**.
///   La console web servant les trois rôles sur une seule origine, le cas est courant : c'est
///   pourquoi l'enregistrement est rejoué à chaque connexion et le jeton détaché à la
///   déconnexion.
///
/// Contrat
/// -------
/// Comme [ParamsService], ce service **ne lève jamais** et reçoit ses dépendances par
/// injection plutôt que d'appeler `Api.instance` : le push est un confort, son indisponibilité
/// ne doit ni bloquer la connexion ni empêcher les tests de s'exécuter sans réseau.
class PushService {
  PushService({
    required this.enregistrer,
    required this.supprimer,
    this.messaging,
  });

  // Champs publics parce que Dart interdit les paramètres nommés préfixés d'un souligné :
  // l'injection par constructeur nommé impose donc de les exposer.

  /// Publie le jeton auprès de MS4.
  final Future<void> Function(String token, String plateforme) enregistrer;

  /// Détache le jeton du compte.
  final Future<void> Function(String token) supprimer;

  /// Instance injectable ; `null` en production, où l'on prend le singleton FCM.
  final FirebaseMessaging? messaging;

  StreamSubscription<String>? _refresh;
  String? _dernierToken;

  /// Jeton actuellement associé au compte connecté (`null` si le push est inactif).
  @visibleForTesting
  String? get dernierToken => _dernierToken;

  FirebaseMessaging get _fcm => messaging ?? FirebaseMessaging.instance;

  /// Plateforme déclarée à MS4. Le champ est purement diagnostique, mais il ne doit pas
  /// mentir : MS4 range en « INCONNU » ce qu'il ne reconnaît pas plutôt que de deviner.
  static String get plateforme {
    if (kIsWeb) return 'WEB';
    return defaultTargetPlatform.name.toUpperCase();
  }

  /// À appeler après une connexion réussie.
  ///
  /// Rejoué à chaque connexion : c'est ce qui réaffecte le jeton au bon compte lorsque
  /// l'appareil change de main.
  Future<void> activer() async {
    try {
      final autorisation = await _fcm.requestPermission();
      if (autorisation.authorizationStatus == AuthorizationStatus.denied) {
        // Refus explicite de l'utilisateur : ce n'est pas une erreur, on n'insiste pas.
        return;
      }

      // La clé VAPID n'est exigée que sur le web ; la passer sur Android est sans effet mais
      // inutile, et une chaîne vide y serait refusée.
      final token = await _fcm.getToken(
        vapidKey: kIsWeb && Env.vapidKey.isNotEmpty ? Env.vapidKey : null,
      );
      if (token == null || token.isEmpty) return;

      await enregistrer(token, plateforme);
      _dernierToken = token;

      // Un jeton tourne (réinstallation, purge du navigateur, rotation Firebase). Sans ce
      // réabonnement, le compte retomberait silencieusement en « aucun device ».
      await _refresh?.cancel();
      _refresh = _fcm.onTokenRefresh.listen((nouveau) async {
        try {
          await enregistrer(nouveau, plateforme);
          _dernierToken = nouveau;
        } catch (_) {
          // Renouvellement manqué : le prochain démarrage rejouera activer().
        }
      });
    } catch (_) {
      // Firebase absent, service worker non enregistré, navigateur sans Push API,
      // MS4 injoignable : l'application reste parfaitement utilisable sans push.
    }
  }

  /// À appeler à la déconnexion, **avant** d'effacer le jeton de session : l'appel est
  /// authentifié. Sans cela, l'appareil continuerait de recevoir les notifications d'un
  /// compte auquel il n'est plus connecté.
  Future<void> desactiver() async {
    final token = _dernierToken;
    _dernierToken = null;
    await _refresh?.cancel();
    _refresh = null;
    if (token == null) return;
    try {
      await supprimer(token);
    } catch (_) {
      // Le serveur désactivera de toute façon le jeton au premier rejet de FCM.
    }
  }
}
