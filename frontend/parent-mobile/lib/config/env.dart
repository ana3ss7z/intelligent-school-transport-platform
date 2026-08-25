/// Configuration d'environnement — surchargée au build via --dart-define.
/// Ex: flutter run --dart-define=GATEWAY=http://192.168.0.5:8080
///                 --dart-define=WS_GPS=ws://192.168.0.5:8083/ws/gps
class Env {
  /// API Gateway (tout le REST passe par là).
  static const String gateway = String.fromEnvironment(
    'GATEWAY',
    defaultValue: 'http://localhost:8080',
  );

  /// WebSocket GPS (direct vers MS3, non proxifié par la Gateway).
  static const String wsGps = String.fromEnvironment(
    'WS_GPS',
    defaultValue: 'ws://localhost:8083/ws/gps',
  );

  // ══ Valeurs pilotées par la console d'administration (MS13) ══════════════
  //
  // Ces réglages étaient des `static const` : les changer imposait de recompiler et de
  // redéployer l'application. Ils sont désormais alimentés par `ParamsService.charger()`
  // au démarrage, via `appliquer()`.
  //
  // Les constantes `_defaut…` ci-dessous ne disparaissent pas pour autant : elles restent
  // le repli hors ligne. L'application doit démarrer sans réseau.
  //
  // Les sites d'appel n'ont pas changé : `Env.ecoleLat` reste `Env.ecoleLat`.

  static const double _defautEcoleLat = 33.893;
  static const double _defautEcoleLng = -5.5455;
  static const Duration _defautPollTrajet = Duration(seconds: 15);
  static const Duration _defautPollEta = Duration(seconds: 30);
  static const Duration _defautPollInbox = Duration(seconds: 15);
  static const Duration _defautPollUnread = Duration(seconds: 20);

  static double _ecoleLat = _defautEcoleLat;
  static double _ecoleLng = _defautEcoleLng;
  static Duration _pollTrajet = _defautPollTrajet;
  static Duration _pollEta = _defautPollEta;
  static Duration _pollInbox = _defautPollInbox;
  static Duration _pollUnread = _defautPollUnread;

  /// École Al Massira (destination des tournées) — comme le web.
  static double get ecoleLat => _ecoleLat;
  static double get ecoleLng => _ecoleLng;

  // Intervalles de polling (miroir du web parent).
  static Duration get pollTrajet => _pollTrajet;
  static Duration get pollEta => _pollEta;
  static Duration get pollInbox => _pollInbox;
  static Duration get pollUnread => _pollUnread;

  /// Applique les valeurs servies par MS13. Toute clé absente ou illisible laisse la valeur
  /// précédente en place : une réponse partielle ne doit pas dégrader ce qui marchait.
  static void appliquer(Map<String, String> v) {
    _ecoleLat = _nombre(v['ecole.lat'], _ecoleLat);
    _ecoleLng = _nombre(v['ecole.lng'], _ecoleLng);
    _pollTrajet = _duree(v['ui.poll_trajet_s'], _pollTrajet);
    _pollEta = _duree(v['ui.poll_eta_s'], _pollEta);
    _pollInbox = _duree(v['ui.poll_inbox_s'], _pollInbox);
    _pollUnread = _duree(v['ui.poll_unread_s'], _pollUnread);
  }

  /// Remet les valeurs compilées. Utilisé par les tests pour repartir d'un état connu.
  static void reinitialiser() {
    _ecoleLat = _defautEcoleLat;
    _ecoleLng = _defautEcoleLng;
    _pollTrajet = _defautPollTrajet;
    _pollEta = _defautPollEta;
    _pollInbox = _defautPollInbox;
    _pollUnread = _defautPollUnread;
  }

  static double _nombre(String? brut, double defaut) {
    if (brut == null || brut.isEmpty) return defaut;
    return double.tryParse(brut) ?? defaut;
  }

  static Duration _duree(String? brut, Duration defaut) {
    if (brut == null || brut.isEmpty) return defaut;
    final s = double.tryParse(brut);
    if (s == null || s <= 0) return defaut;
    // Plancher de 5 s, comme côté web : la passerelle plafonne à 20 requêtes/s par adresse,
    // et plusieurs sondages tournent en parallèle dans l'application.
    return Duration(milliseconds: (s.clamp(5, 3600) * 1000).round());
  }

  // Timeouts réseau.
  static const Duration httpTimeout = Duration(seconds: 20);
  static const Duration httpLongTimeout = Duration(seconds: 120); // ETA + LLM
}
