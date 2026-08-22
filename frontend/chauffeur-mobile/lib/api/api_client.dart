import 'package:dio/dio.dart';

import '../models/models.dart';

/// Contrat de la couche réseau.
///
/// L'app parent expose un singleton `Api.instance`, ce qui la rend intestable
/// au-delà de l'écran de login. Ici on passe par une interface : les écrans
/// lisent `ref.read(apiProvider)` et les tests injectent un faux client.
abstract class ApiClient {
  /// JWT courant, injecté par le contrôleur d'auth.
  set token(String? value);

  /// Appelé sur 401 (session expirée) → logout + retour login.
  set onUnauthorized(void Function()? cb);

  // ── Auth ──
  Future<AuthUser> login(String email, String motDePasse);

  // ── Bus & élèves ──
  Future<List<Bus>> getBus();

  /// Élèves du bus **dans l'ordre de passage** (MS2, ADMIN/CHAUFFEUR).
  Future<List<Eleve>> getElevesParBus(int busId);

  /// Présence — valeur **absolue**, pas un toggle : l'appel est donc idempotent
  /// et peut être rejoué sans risque par la file hors ligne.
  Future<void> setPresence(int eleveId, bool present);

  // ── Trajets (MS1) ──
  /// Trajet en cours du chauffeur connecté, ou null (HTTP 204).
  Future<Trajet?> getMonTrajetActif();

  Future<List<Trajet>> getMesTrajets();

  /// Démarre un trajet.
  ///
  /// [geometrie] et [groupeId] ne sont pas décoratifs : MS1 les persiste et MS11
  /// s'en sert comme référence pour détecter une déviation d'itinéraire (UC-8).
  /// Démarrer sans géométrie casse cette surveillance **en silence**.
  Future<Trajet> demarrerTrajet({
    required int busId,
    required String sens, // MATIN | SOIR
    int? groupeId,
    List<List<double>>? geometrie,
    double? distancePlanM,
    double? dureePlanMin,
  });

  Future<Trajet> terminerTrajet(int trajetId);

  /// Tournée **figée au démarrage** du trajet en cours d'un bus, ou null (204).
  ///
  /// C'est la même polyligne que celle lue par l'app parent : en calculant
  /// l'ETA dessus plutôt que sur la tournée fraîchement re-planifiée, chauffeur
  /// et parents affichent le même chiffre.
  Future<TrajetRoute?> getTrajetRoute(int busId);

  // ── Planification (MS5) ──
  Future<TourneePlan> getTournee(int groupeId, String sens);

  // ── ETA (MS12) ──
  Future<EtaResult> predictEta({
    double? busLat,
    double? busLng,
    double? destLat,
    double? destLng,
    double? distanceRoutiereM,
    double? dureeBaseS,
    double? heureDepart,
    required String moment, // matin | soir
  });

  // ── GPS (MS3) ──
  Future<GpsPosition?> getDernierePositionBus(int busId);

  /// Publie la position du téléphone comme position du bus.
  Future<void> publierPosition({
    required int busId,
    required double latitude,
    required double longitude,
    double? vitesse,
    double? cap,
    double? precision,
  });

  // ── Incidents (MS10) ──
  Future<List<Incident>> getIncidentsParBus(int busId);

  Future<Incident> creerIncident({
    required String type,
    required int busId,
    String? description,
    double? latitude,
    double? longitude,
  });

  // ── Messagerie (MS4) ──
  Future<List<MessageItem>> getMaConversation();

  Future<MessageItem> envoyerMessage(String contenu);

  /// Diffusion à tous les parents du groupe du bus.
  Future<int> diffuserAuxParents(int busId, String contenu);

  Future<int> getUnreadCount();

  // ── Notifications (MS4) ──
  Future<List<NotificationItem>> getMesNotifications();
}

/// Erreur métier renvoyée par le backend (message déjà lisible).
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  ApiException(this.message, {this.statusCode});
  @override
  String toString() => message;
}

/// Le serveur n'a pas pu être joint (pas de réseau, DNS, timeout de connexion).
///
/// Distinguée d'[ApiException] parce que la décision n'est pas la même : une
/// erreur métier doit remonter au chauffeur, une coupure réseau doit partir en
/// file d'attente et être rejouée.
class OfflineException implements Exception {
  final String message;
  OfflineException([this.message = 'Hors ligne']);
  @override
  String toString() => message;
}

/// Vrai si l'échec vient du transport et non d'une réponse du serveur.
bool isOffline(Object e) {
  if (e is OfflineException) return true;
  if (e is DioException) {
    return e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.sendTimeout ||
        e.type == DioExceptionType.receiveTimeout;
  }
  return false;
}

/// Convertit une erreur en message lisible (FR).
String friendlyError(Object e) {
  if (e is ApiException) return e.message;
  if (e is OfflineException) return e.message;
  if (e is DioException) {
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout) {
      return 'Délai dépassé. Vérifiez la connexion au serveur.';
    }
    if (e.type == DioExceptionType.connectionError) {
      return "Impossible de joindre le serveur. Vérifiez le Wi-Fi et l'adresse.";
    }
    final data = e.response?.data;
    if (data is Map) {
      final m = (data['detail'] ?? data['error'] ?? data['message'])
          ?.toString();
      if (m != null && m.isNotEmpty) return m;
    }
    if (data is String && data.trim().isNotEmpty) return data;
    return 'Erreur réseau (${e.response?.statusCode ?? '—'}).';
  }
  return e.toString();
}
