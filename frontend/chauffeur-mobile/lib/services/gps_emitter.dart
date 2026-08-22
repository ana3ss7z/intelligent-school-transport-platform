import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import '../config/env.dart';

/// État lisible de l'émission, pour l'UI.
enum GpsEmitterState {
  /// Interrupteur sur off — c'est `bus_simulator.py` qui fait foi.
  off,

  /// Activé, mais aucun trajet en cours : rien à émettre.
  enAttente,

  /// Positions envoyées à MS3.
  emission,

  /// Permission refusée, service désactivé, ou erreur réseau persistante.
  bloque,
}

/// Publie la position du téléphone du chauffeur comme position de SON bus.
///
/// Cycle de vie : émet uniquement si (1) l'interrupteur est activé **et**
/// (2) un trajet est en cours. Hors trajet, un bus n'a pas à bouger.
///
/// L'interrupteur est **désactivé par défaut** : la démo de soutenance tourne au
/// simulateur, et deux sources GPS concurrentes sur le même bus se battraient.
///
/// Ce que cette classe n'essaie PAS de faire : rattraper les points perdus.
/// `PositionRequest` (MS3) n'a pas de champ horodatage — le serveur date à la
/// réception. Réémettre un point vieux de trois minutes écrirait donc une
/// **fausse position courante**, bien pire qu'un trou dans la trace.
class GpsEmitter extends ChangeNotifier {
  GpsEmitter(this._api);

  static const _prefKey = 'gps_emission_active';

  /// `bus_simulator.py` publie des **km/h** (40 normal, 110 pour déclencher
  /// l'anomalie ; seuil MS11 = 90 km/h) alors que `geolocator` renvoie des m/s.
  /// Sans cette conversion, la vitesse du bus réel serait 3,6× trop faible et
  /// « VITESSE_EXCESSIVE » ne se déclencherait jamais depuis un téléphone.
  static const _msVersKmh = 3.6;

  final ApiClient _api;

  StreamSubscription<Position>? _sub;
  DateTime? _dernierEnvoi;

  bool _enabled = false;
  bool _trajetActif = false;
  int? _busId;
  String _matricule = '';

  String? _erreur;
  int _envoyees = 0;
  Position? _derniere;

  bool get enabled => _enabled;
  String? get erreur => _erreur;
  int get envoyees => _envoyees;
  Position? get derniere => _derniere;

  GpsEmitterState get etat {
    if (_erreur != null) return GpsEmitterState.bloque;
    if (!_enabled) return GpsEmitterState.off;
    return _sub != null ? GpsEmitterState.emission : GpsEmitterState.enAttente;
  }

  /// Restaure le choix du chauffeur (l'interrupteur survit au redémarrage).
  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _enabled = prefs.getBool(_prefKey) ?? false;
    notifyListeners();
    unawaited(_reevaluer());
  }

  Future<void> setEnabled(bool value) async {
    if (_enabled == value) return;
    _enabled = value;
    _erreur = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_prefKey, value);
    notifyListeners();
    await _reevaluer();
  }

  /// Informe l'émetteur du contexte courant (appelé par l'écran de tournée).
  void bind({int? busId, required bool trajetActif, String matricule = ''}) {
    final change = busId != _busId || trajetActif != _trajetActif;
    _busId = busId;
    _trajetActif = trajetActif;
    _matricule = matricule;
    if (change) unawaited(_reevaluer());
  }

  Future<void> _reevaluer() async {
    final doitEmettre = _enabled && _trajetActif && _busId != null;
    if (doitEmettre && _sub == null) {
      await _demarrer();
    } else if (!doitEmettre && _sub != null) {
      await _arreter();
    }
  }

  Future<void> _demarrer() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        _fail('La localisation est désactivée sur l\'appareil.');
        return;
      }
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied) {
        _fail('Permission de localisation refusée.');
        return;
      }
      if (permission == LocationPermission.deniedForever) {
        _fail(
          'Permission refusée définitivement — à réactiver dans les réglages.',
        );
        return;
      }

      _sub = Geolocator.getPositionStream(
        locationSettings: _settings(),
      ).listen(_onPosition, onError: (Object e) => _fail(e.toString()));

      _erreur = null;
      notifyListeners();
    } catch (e) {
      _fail(friendlyError(e));
    }
  }

  /// Sur Android, `foregroundNotificationConfig` fait tenir au plugin un service
  /// de premier plan lié au flux : les positions continuent d'arriver écran
  /// verrouillé, **sans** demander ACCESS_BACKGROUND_LOCATION (la permission
  /// « tout le temps », qui exige une justification Play Store et un second
  /// écran de consentement sur Android 11+).
  LocationSettings _settings() {
    if (kIsWeb) {
      return LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: Env.gpsDistanceFilterM,
      );
    }
    if (defaultTargetPlatform == TargetPlatform.android) {
      return AndroidSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: Env.gpsDistanceFilterM,
        foregroundNotificationConfig: ForegroundNotificationConfig(
          notificationTitle: 'Trajet en cours',
          notificationText: _matricule.isEmpty
              ? 'Position transmise à l\'administration'
              : 'Bus $_matricule — position transmise',
          enableWakeLock: true,
        ),
      );
    }
    return LocationSettings(
      accuracy: LocationAccuracy.high,
      distanceFilter: Env.gpsDistanceFilterM,
    );
  }

  Future<void> _onPosition(Position p) async {
    _derniere = p;

    // Le `distanceFilter` borne déjà le débit dans l'espace ; ce plafond le
    // borne dans le temps (bus à l'arrêt qui « vibre » sur sa position GPS).
    final maintenant = DateTime.now();
    if (_dernierEnvoi != null &&
        maintenant.difference(_dernierEnvoi!) < Env.gpsMinInterval) {
      return;
    }
    final busId = _busId;
    if (busId == null || !_enabled || !_trajetActif) return;
    _dernierEnvoi = maintenant;

    try {
      await _api.publierPosition(
        busId: busId,
        latitude: p.latitude,
        longitude: p.longitude,
        vitesse: p.speed.isFinite && p.speed >= 0
            ? (p.speed * _msVersKmh).clamp(0, 300).toDouble()
            : null,
        cap: p.heading.isFinite && p.heading >= 0
            ? p.heading.clamp(0, 360).toDouble()
            : null,
        precision: p.accuracy.isFinite && p.accuracy >= 0 ? p.accuracy : null,
      );
      _envoyees++;
      if (_erreur != null) _erreur = null;
      notifyListeners();
    } catch (e) {
      // Un point non transmis n'est pas rejoué (cf. docstring de la classe).
      // On ne signale que ce qui n'est pas une simple coupure : hors ligne,
      // l'app affiche déjà son bandeau réseau.
      if (!isOffline(e)) {
        _erreur = friendlyError(e);
        notifyListeners();
      }
    }
  }

  void _fail(String message) {
    _erreur = message;
    notifyListeners();
  }

  Future<void> _arreter() async {
    await _sub?.cancel();
    _sub = null;
    _dernierEnvoi = null;
    notifyListeners();
  }

  /// Ouvre les réglages système (permission refusée définitivement).
  Future<void> ouvrirReglages() => Geolocator.openAppSettings();

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}
