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

  /// École Al Massira (destination des tournées) — comme le web.
  static const double ecoleLat = 33.893;
  static const double ecoleLng = -5.5455;

  // Intervalles de polling (miroir du web parent).
  static const Duration pollTrajet = Duration(seconds: 15);
  static const Duration pollEta = Duration(seconds: 30);
  static const Duration pollInbox = Duration(seconds: 15);
  static const Duration pollUnread = Duration(seconds: 20);

  // Timeouts réseau.
  static const Duration httpTimeout = Duration(seconds: 20);
  static const Duration httpLongTimeout = Duration(seconds: 120); // ETA + LLM
}
