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

  // Intervalles de polling (miroir du web chauffeur).
  static const Duration pollTrajet = Duration(seconds: 15);
  static const Duration pollEta = Duration(seconds: 30);
  static const Duration pollInbox = Duration(seconds: 15);
  static const Duration pollUnread = Duration(seconds: 20);

  /// Présence des élèves — elle change AUSSI hors de l'app (simulateur, admin,
  /// autre appareil), d'où un rafraîchissement plus serré que le reste.
  static const Duration pollPresence = Duration(seconds: 10);

  /// Fil de discussion avec l'administration.
  static const Duration pollConversation = Duration(seconds: 10);

  // ── Émission GPS (le téléphone du chauffeur est la source réelle) ──
  /// Débit maximal des POST /api/gps/position.
  static const Duration gpsMinInterval = Duration(seconds: 5);

  /// Déplacement minimal (m) avant qu'une nouvelle position soit émise.
  static const int gpsDistanceFilterM = 15;

  // ── File d'attente hors ligne ──
  /// Filet de sécurité si aucun événement de connectivité n'arrive.
  static const Duration outboxSweep = Duration(seconds: 30);

  /// Au-delà, l'item est « parké » et la décision revient au chauffeur —
  /// pas de réessai infini silencieux sur une écriture non idempotente.
  static const int outboxMaxAttempts = 3;

  // Timeouts réseau.
  static const Duration httpTimeout = Duration(seconds: 20);
  static const Duration httpLongTimeout = Duration(seconds: 120); // ETA + VRP
}
