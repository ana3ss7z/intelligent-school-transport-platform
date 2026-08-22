import 'package:dio/dio.dart';

import '../config/env.dart';
import '../models/models.dart';
import 'api_client.dart';

/// Implémentation Dio d'[ApiClient] — toutes les routes consommées par l'app chauffeur.
///
/// - Injecte `Authorization: Bearer <token>` sur chaque requête.
/// - Sur 401 → déclenche [onUnauthorized] (logout + retour login).
/// - `validateStatus < 500` : les 204 et les 4xx reviennent en réponse normale,
///   on les traite explicitement (204 = « pas de trajet », 4xx = erreur métier).
class DioApi implements ApiClient {
  DioApi({Dio? dio}) {
    _dio = dio ?? _build();
  }

  late final Dio _dio;

  String? _token;
  void Function()? _onUnauthorized;

  @override
  set token(String? value) => _token = value;

  @override
  set onUnauthorized(void Function()? cb) => _onUnauthorized = cb;

  Dio _build() {
    final dio = Dio(
      BaseOptions(
        baseUrl: Env.gateway,
        connectTimeout: Env.httpTimeout,
        receiveTimeout: Env.httpTimeout,
        sendTimeout: Env.httpTimeout,
        validateStatus: (s) => s != null && s < 500,
      ),
    );
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (_token != null && _token!.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $_token';
          }
          handler.next(options);
        },
        onResponse: (response, handler) {
          if (response.statusCode == 401) _onUnauthorized?.call();
          handler.next(response);
        },
        onError: (e, handler) {
          if (e.response?.statusCode == 401) _onUnauthorized?.call();
          handler.next(e);
        },
      ),
    );
    return dio;
  }

  /// Appels lourds : MS5 (OR-Tools + OSRM) et MS12.
  Options get _long => Options(
    receiveTimeout: Env.httpLongTimeout,
    sendTimeout: Env.httpLongTimeout,
  );

  // ─────────────────────────────────────────────────────────────── Auth
  @override
  Future<AuthUser> login(String email, String motDePasse) async {
    final r = await _dio.post(
      '/api/auth/login',
      data: {'email': email, 'motDePasse': motDePasse},
    );
    if (r.statusCode == 200 && r.data is Map) {
      return AuthUser.fromJson(Map<String, dynamic>.from(r.data as Map));
    }
    throw ApiException(
      _msg(r) ?? 'Email ou mot de passe incorrect.',
      statusCode: r.statusCode,
    );
  }

  // ──────────────────────────────────────────────────── Bus & élèves
  @override
  Future<List<Bus>> getBus() async {
    final r = await _dio.get('/api/bus');
    _ensureOk(r);
    return _list(r).map(Bus.fromJson).toList();
  }

  @override
  Future<List<Eleve>> getElevesParBus(int busId) async {
    final r = await _dio.get('/api/eleves/bus/$busId');
    _ensureOk(r);
    return _list(r).map(Eleve.fromJson).toList();
  }

  @override
  Future<void> setPresence(int eleveId, bool present) async {
    final r = await _dio.patch(
      '/api/eleves/$eleveId/presence',
      queryParameters: {'present': present},
    );
    _ensureOk(r);
  }

  // ──────────────────────────────────────────────────────────── Trajets
  @override
  Future<Trajet?> getMonTrajetActif() async {
    final r = await _dio.get('/api/trajets/mon-actif');
    if (r.statusCode == 204 || r.data == null || r.data == '') return null;
    _ensureOk(r);
    if (r.data is Map) {
      return Trajet.fromJson(Map<String, dynamic>.from(r.data as Map));
    }
    return null;
  }

  @override
  Future<List<Trajet>> getMesTrajets() async {
    final r = await _dio.get('/api/trajets/mes-trajets');
    _ensureOk(r);
    return _list(r).map(Trajet.fromJson).toList();
  }

  @override
  Future<Trajet> demarrerTrajet({
    required int busId,
    required String sens,
    int? groupeId,
    List<List<double>>? geometrie,
    double? distancePlanM,
    double? dureePlanMin,
  }) async {
    final r = await _dio.post(
      '/api/trajets/demarrer',
      data: {
        'busId': busId,
        'sens': sens,
        'groupeId': ?groupeId,
        'geometrie': ?geometrie,
        'distancePlanM': ?distancePlanM,
        'dureePlanMin': ?dureePlanMin,
      },
    );
    _ensureOk(r);
    return Trajet.fromJson(Map<String, dynamic>.from(r.data as Map));
  }

  @override
  Future<Trajet> terminerTrajet(int trajetId) async {
    final r = await _dio.post('/api/trajets/$trajetId/terminer');
    _ensureOk(r);
    return Trajet.fromJson(Map<String, dynamic>.from(r.data as Map));
  }

  @override
  Future<TrajetRoute?> getTrajetRoute(int busId) async {
    final r = await _dio.get('/api/trajets/bus/$busId/route');
    if (r.statusCode == 204 || r.data == null || r.data == '') return null;
    _ensureOk(r);
    if (r.data is Map) {
      return TrajetRoute.fromJson(Map<String, dynamic>.from(r.data as Map));
    }
    return null;
  }

  // ───────────────────────────────────────────────────── Planification
  @override
  Future<TourneePlan> getTournee(int groupeId, String sens) async {
    final r = await _dio.post(
      '/api/planification/tournee',
      queryParameters: {'groupeId': groupeId, 'sens': sens},
      options: _long,
    );
    _ensureOk(r);
    return TourneePlan.fromJson(Map<String, dynamic>.from(r.data as Map));
  }

  // ─────────────────────────────────────────────────────────────── ETA
  @override
  Future<EtaResult> predictEta({
    double? busLat,
    double? busLng,
    double? destLat,
    double? destLng,
    double? distanceRoutiereM,
    double? dureeBaseS,
    double? heureDepart,
    required String moment,
  }) async {
    final r = await _dio.post(
      '/api/eta/predict',
      data: {
        'auto_context': true,
        'moment': moment,
        'heure_depart': ?heureDepart,
        'distance_routiere_m': ?distanceRoutiereM,
        'duree_base_s': ?dureeBaseS,
        // Mode coordonnées : uniquement si on n'a pas déjà mesuré la portion
        // restante sur le circuit.
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
    throw ApiException(_msg(r) ?? 'ETA indisponible', statusCode: r.statusCode);
  }

  // ─────────────────────────────────────────────────────────────── GPS
  @override
  Future<GpsPosition?> getDernierePositionBus(int busId) async {
    final r = await _dio.get('/api/gps/bus/$busId/derniere');
    if (r.statusCode == 200 && r.data is Map) {
      return GpsPosition.fromJson(Map<String, dynamic>.from(r.data as Map));
    }
    return null;
  }

  @override
  Future<void> publierPosition({
    required int busId,
    required double latitude,
    required double longitude,
    double? vitesse,
    double? cap,
    double? precision,
  }) async {
    final r = await _dio.post(
      '/api/gps/position',
      data: {
        'cibleType': 'BUS',
        'cibleId': busId,
        'latitude': latitude,
        'longitude': longitude,
        'vitesse': ?vitesse,
        'cap': ?cap,
        'precision': ?precision,
      },
    );
    _ensureOk(r);
  }

  // ───────────────────────────────────────────────────────── Incidents
  @override
  Future<List<Incident>> getIncidentsParBus(int busId) async {
    final r = await _dio.get('/api/incidents/bus/$busId');
    _ensureOk(r);
    return _list(r).map(Incident.fromJson).toList();
  }

  @override
  Future<Incident> creerIncident({
    required String type,
    required int busId,
    String? description,
    double? latitude,
    double? longitude,
  }) async {
    final r = await _dio.post(
      '/api/incidents',
      data: {
        'type': type,
        'busId': busId,
        'description': ?description,
        'latitude': ?latitude,
        'longitude': ?longitude,
      },
    );
    _ensureOk(r);
    return Incident.fromJson(Map<String, dynamic>.from(r.data as Map));
  }

  // ──────────────────────────────────────────────────────── Messagerie
  @override
  Future<List<MessageItem>> getMaConversation() async {
    final r = await _dio.get('/api/messages/ma-conversation');
    _ensureOk(r);
    return _list(r).map(MessageItem.fromJson).toList();
  }

  @override
  Future<MessageItem> envoyerMessage(String contenu) async {
    final r = await _dio.post('/api/messages', data: {'contenu': contenu});
    _ensureOk(r);
    return MessageItem.fromJson(Map<String, dynamic>.from(r.data as Map));
  }

  @override
  Future<int> diffuserAuxParents(int busId, String contenu) async {
    final r = await _dio.post(
      '/api/messages/diffusion',
      queryParameters: {'busId': busId},
      data: {'contenu': contenu},
    );
    _ensureOk(r);
    if (r.data is Map && (r.data as Map)['parents'] != null) {
      return ((r.data as Map)['parents'] as num).toInt();
    }
    return 0;
  }

  @override
  Future<int> getUnreadCount() async {
    final r = await _dio.get('/api/messages/non-lus');
    if (r.data is Map && (r.data as Map)['count'] != null) {
      return ((r.data as Map)['count'] as num).toInt();
    }
    return 0;
  }

  // ────────────────────────────────────────────────────── Notifications
  @override
  Future<List<NotificationItem>> getMesNotifications() async {
    final r = await _dio.get('/api/notifications/mes-notifications');
    _ensureOk(r);
    return _list(r).map(NotificationItem.fromJson).toList();
  }

  // ─────────────────────────────────────────────────────────── Helpers
  /// `validateStatus < 500` fait remonter les 4xx en réponse normale : sans ce
  /// garde-fou, une écriture refusée passerait pour un succès.
  void _ensureOk(Response r) {
    final code = r.statusCode ?? 0;
    if (code >= 200 && code < 300) return;
    throw ApiException(
      _msg(r) ?? 'Erreur serveur ($code).',
      statusCode: r.statusCode,
    );
  }

  List<Map<String, dynamic>> _list(Response r) {
    if (r.data is List) {
      return (r.data as List)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
    }
    return const [];
  }

  /// Extrait le message backend (FastAPI `detail` ou Spring `error`/texte brut).
  String? _msg(Response r) {
    final d = r.data;
    if (d is Map) {
      return (d['detail'] ?? d['error'] ?? d['message'])?.toString();
    }
    if (d is String && d.trim().isNotEmpty) return d;
    return null;
  }
}
