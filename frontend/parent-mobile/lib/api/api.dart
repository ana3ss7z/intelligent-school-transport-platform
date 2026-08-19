import 'package:dio/dio.dart';

import '../config/env.dart';
import '../models/models.dart';

/// Client HTTP unique (Dio) + toutes les routes consommées par l'app parent.
///
/// - Injecte `Authorization: Bearer <token>` sur chaque requête.
/// - Sur 401 → déclenche [onUnauthorized] (logout + retour login).
class Api {
  Api._();
  static final Api instance = Api._();

  /// JWT courant (mis à jour par le contrôleur d'auth).
  String? token;

  /// Callback branché au démarrage pour gérer l'expiration de session.
  void Function()? onUnauthorized;

  late final Dio _dio = _build();

  Dio _build() {
    final dio = Dio(
      BaseOptions(
        baseUrl: Env.gateway,
        connectTimeout: Env.httpTimeout,
        receiveTimeout: Env.httpTimeout,
        sendTimeout: Env.httpTimeout,
        // On gère nous-mêmes 204/erreurs métier.
        validateStatus: (s) => s != null && s < 500,
      ),
    );
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (token != null && token!.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onResponse: (response, handler) {
          if (response.statusCode == 401) {
            onUnauthorized?.call();
          }
          handler.next(response);
        },
        onError: (e, handler) {
          if (e.response?.statusCode == 401) {
            onUnauthorized?.call();
          }
          handler.next(e);
        },
      ),
    );
    return dio;
  }

  Options get _long => Options(
    receiveTimeout: Env.httpLongTimeout,
    sendTimeout: Env.httpLongTimeout,
  );

  // ---------------------------------------------------------------- Auth
  Future<AuthUser> login(String email, String motDePasse) async {
    final r = await _dio.post(
      '/api/auth/login',
      data: {'email': email, 'motDePasse': motDePasse},
    );
    if (r.statusCode == 200 && r.data is Map) {
      return AuthUser.fromJson(Map<String, dynamic>.from(r.data as Map));
    }
    throw ApiException(_msg(r) ?? 'Email ou mot de passe incorrect.');
  }

  // ------------------------------------------------------------- Enfants
  Future<List<Eleve>> getMesEnfants(int parentId) async {
    final r = await _dio.get('/api/eleves/parent/$parentId');
    return _list(r).map((e) => Eleve.fromJson(e)).toList();
  }

  Future<List<Bus>> getBus() async {
    final r = await _dio.get('/api/bus');
    return _list(r).map((e) => Bus.fromJson(e)).toList();
  }

  // ------------------------------------------------------------- Trajets
  /// Trajet actif d'un bus, ou null (HTTP 204 = aucun trajet en cours).
  Future<Trajet?> getTrajetActifBus(int busId) async {
    final r = await _dio.get('/api/trajets/bus/$busId/actif');
    if (r.statusCode == 204 || r.data == null || r.data == '') return null;
    if (r.data is Map) {
      return Trajet.fromJson(Map<String, dynamic>.from(r.data as Map));
    }
    return null;
  }

  /// Tournée figée du trajet en cours d'un bus, ou null (HTTP 204 = aucun trajet).
  Future<TrajetRoute?> getTrajetRoute(int busId) async {
    final r = await _dio.get('/api/trajets/bus/$busId/route');
    if (r.statusCode == 204 || r.data == null || r.data == '') return null;
    if (r.data is Map) {
      return TrajetRoute.fromJson(Map<String, dynamic>.from(r.data as Map));
    }
    return null;
  }

  // --------------------------------------------------------- Planification
  /// Étapes de la tournée pour MES enfants (MS5 — portée imposée par le JWT).
  Future<List<EtapeEnfant>> getEtaMesEnfants(String sens) async {
    final r = await _dio.post(
      '/api/planification/mes-enfants',
      queryParameters: {'sens': sens},
      options: _long,
    );
    if (r.statusCode == 200 && r.data is Map) {
      final liste = (r.data as Map)['enfants'] as List? ?? const [];
      return liste
          .map((e) => EtapeEnfant.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
    }
    throw ApiException(_msg(r) ?? 'Prévisions indisponibles');
  }

  // ------------------------------------------------------------------ ETA
  /// Prédit l'ETA (MS12).
  ///
  /// Deux modes exclusifs : soit les coordonnées (OSRM route en direct), soit
  /// [distanceRoutiereM] + [dureeBaseS] déjà mesurés — c'est ce second mode qui permet
  /// de donner la portion **restante sur la tournée** au lieu du vol d'oiseau.
  Future<EtaResult> predictEta({
    double? busLat,
    double? busLng,
    double? destLat,
    double? destLng,
    double? distanceRoutiereM,
    double? dureeBaseS,
    double?
    heureDepart, // heure décimale (7.5 = 07:30) ; défaut MS12 selon `moment`
    required String moment, // matin | soir
  }) async {
    final r = await _dio.post(
      '/api/eta/predict',
      data: {
        'auto_context': true,
        'moment': moment,
        'heure_depart': ?heureDepart,
        'distance_routiere_m': ?distanceRoutiereM,
        'duree_base_s': ?dureeBaseS,
        if (distanceRoutiereM == null) ...{
          'bus_lat': busLat,
          'bus_lng': busLng,
          'dest_lat': destLat,
          'dest_lng': destLng,
        },
      },
      options: _long,
    );
    if (r.statusCode == 200 && r.data is Map) {
      return EtaResult.fromJson(Map<String, dynamic>.from(r.data as Map));
    }
    throw ApiException(_msg(r) ?? 'ETA indisponible');
  }

  // ------------------------------------------------------- GPS (fallback)
  Future<GpsPosition?> getDernierePositionBus(int busId) async {
    final r = await _dio.get('/api/gps/bus/$busId/derniere');
    if (r.statusCode == 200 && r.data is Map) {
      return GpsPosition.fromJson(Map<String, dynamic>.from(r.data as Map));
    }
    return null;
  }

  // ---------------------------------------------------------- Messagerie
  Future<List<MessageItem>> getParentInbox() async {
    final r = await _dio.get('/api/messages/parent');
    return _list(r).map((e) => MessageItem.fromJson(e)).toList();
  }

  Future<int> getUnreadCount() async {
    final r = await _dio.get('/api/messages/non-lus');
    if (r.data is Map && (r.data as Map)['count'] != null) {
      return ((r.data as Map)['count'] as num).toInt();
    }
    return 0;
  }

  // -------------------------------------------------------- Notifications
  Future<List<NotificationItem>> getMesNotifications() async {
    final r = await _dio.get('/api/notifications/mes-notifications');
    return _list(r).map((e) => NotificationItem.fromJson(e)).toList();
  }

  // -------------------------------------------------------- Assistant LLM
  Future<ChatReply> chat(String message, List<ChatTurn> history) async {
    final r = await _dio.post(
      '/api/llm/chat',
      data: {
        'message': message,
        'history': history.map((t) => t.toJson()).toList(),
      },
      options: _long,
    );
    if (r.statusCode == 200 && r.data is Map) {
      return ChatReply.fromJson(Map<String, dynamic>.from(r.data as Map));
    }
    throw ApiException(
      _msg(r) ?? "L'assistant est momentanément indisponible.",
    );
  }

  // --------------------------------------------------------------- Helpers
  List<Map<String, dynamic>> _list(Response r) {
    if (r.data is List) {
      return (r.data as List)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
    }
    return const [];
  }

  /// Extrait le message d'erreur backend (FastAPI `detail` ou Spring `error`/texte).
  String? _msg(Response r) {
    final d = r.data;
    if (d is Map) {
      return (d['detail'] ?? d['error'] ?? d['message'])?.toString();
    }
    if (d is String && d.trim().isNotEmpty) return d;
    return null;
  }
}

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}

/// Convertit une erreur Dio en message lisible (FR).
String friendlyError(Object e) {
  if (e is ApiException) return e.message;
  if (e is DioException) {
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout) {
      return 'Délai dépassé. Vérifiez la connexion au serveur.';
    }
    if (e.type == DioExceptionType.connectionError) {
      return 'Impossible de joindre le serveur. Vérifiez le Wi-Fi et l\'adresse.';
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
