import 'package:chauffeur_app/api/api_client.dart';
import 'package:chauffeur_app/models/models.dart';

/// Client réseau simulé.
///
/// C'est ce que l'app parent n'a pas : son `Api.instance` est un singleton, donc
/// ses tests s'arrêtent au login. Ici tout passe par [ApiClient], on peut donc
/// tester les écrans à écritures — y compris les chemins d'échec, qui sont
/// justement ceux qu'on ne verra jamais en démo.
class FakeApi implements ApiClient {
  FakeApi({
    List<Bus>? buses,
    List<Eleve>? eleves,
    TourneePlan? tournee,
    this.trajetActif,
  }) : buses = buses ?? [busParDefaut],
       eleves = eleves ?? elevesParDefaut(),
       tournee = tournee ?? tourneeParDefaut;

  // ── Données servies ──
  List<Bus> buses;
  List<Eleve> eleves;
  TourneePlan tournee;
  Trajet? trajetActif;
  List<Incident> incidents = [];
  List<MessageItem> conversation = [];
  List<NotificationItem> notifications = [];
  List<Trajet> historique = [];
  int unread = 0;

  // ── Scénarios d'échec, un par opération ──
  Object? echecPresence;
  Object? echecDemarrer;
  Object? echecTerminer;
  Object? echecIncident;
  Object? echecMessage;
  Object? echecDiffusion;
  Object? echecTournee;
  Object? echecLogin;
  Object? echecUnread;

  /// Bloque `setPresence` jusqu'à ce que le test le décide — sert à observer
  /// l'état optimiste *pendant* que l'appel est en vol.
  Future<void>? presenceEnAttente;

  /// Idem pour la planification : maintient l'écran ETA sur son état de
  /// chargement, le temps de vérifier que le squelette se rend correctement.
  Future<void>? tourneeEnAttente;

  // ── Journal des appels (assertions) ──
  final List<Map<String, dynamic>> demarrages = [];
  final List<Map<String, dynamic>> presences = [];
  final List<String> messagesEnvoyes = [];
  final List<Map<String, dynamic>> incidentsCrees = [];
  final List<Map<String, dynamic>> diffusions = [];
  final List<Map<String, dynamic>> positions = [];
  int appelsMonActif = 0;

  @override
  set token(String? value) {}

  @override
  set onUnauthorized(void Function()? cb) {}

  static final busParDefaut = Bus(
    id: 7,
    matricule: 'MEK-107',
    capacite: 50,
    statut: 'ACTIF',
    chauffeurId: 42,
    latitude: 33.89,
    longitude: -5.55,
  );

  static List<Eleve> elevesParDefaut() => [
    Eleve(
      id: 1,
      prenom: 'Amine',
      nom: 'Idrissi',
      latitude: 33.895,
      longitude: -5.548,
      groupeId: 3,
      busId: 7,
      ordrePassage: 1,
    ),
    Eleve(
      id: 2,
      prenom: 'Salma',
      nom: 'Bennani',
      latitude: 33.897,
      longitude: -5.552,
      groupeId: 3,
      busId: 7,
      ordrePassage: 2,
    ),
    Eleve(
      id: 3,
      prenom: 'Youssef',
      nom: 'Alaoui',
      latitude: 33.899,
      longitude: -5.556,
      groupeId: 3,
      busId: 7,
      ordrePassage: 3,
    ),
  ];

  static const tourneeParDefaut = TourneePlan(
    sens: 'matin',
    ordre: [1, 2, 3],
    etapes: [
      EtapeTournee(eleveId: 1, rang: 1, cumulDureeS: 300, cumulDistanceM: 1500),
      EtapeTournee(eleveId: 2, rang: 2, cumulDureeS: 600, cumulDistanceM: 3000),
      EtapeTournee(eleveId: 3, rang: 3, cumulDureeS: 900, cumulDistanceM: 4500),
    ],
    geometrie: [
      [33.893, -5.5455],
      [33.895, -5.548],
      [33.897, -5.552],
      [33.899, -5.556],
      [33.893, -5.5455],
    ],
    distanceM: 6000,
    dureeMin: 20,
  );

  static final utilisateur = AuthUser(
    token: 'jwt-de-test',
    userId: 42,
    nom: 'Hassan Chauffeur',
    email: 'hassan@transport.ma',
    role: 'CHAUFFEUR',
  );

  // ── Implémentation ──

  @override
  Future<AuthUser> login(String email, String motDePasse) async {
    if (echecLogin != null) throw echecLogin!;
    return utilisateur;
  }

  @override
  Future<List<Bus>> getBus() async => buses;

  @override
  Future<List<Eleve>> getElevesParBus(int busId) async =>
      eleves.where((e) => e.busId == busId).toList();

  @override
  Future<void> setPresence(int eleveId, bool present) async {
    if (presenceEnAttente != null) await presenceEnAttente;
    if (echecPresence != null) throw echecPresence!;
    presences.add({'eleveId': eleveId, 'present': present});
    eleves = [
      for (final e in eleves)
        if (e.id == eleveId) e.copyWith(statutPresence: present) else e,
    ];
  }

  @override
  Future<Trajet?> getMonTrajetActif() async {
    appelsMonActif++;
    return trajetActif;
  }

  @override
  Future<List<Trajet>> getMesTrajets() async => historique;

  @override
  Future<Trajet> demarrerTrajet({
    required int busId,
    required String sens,
    int? groupeId,
    List<List<double>>? geometrie,
    double? distancePlanM,
    double? dureePlanMin,
  }) async {
    demarrages.add({
      'busId': busId,
      'sens': sens,
      'groupeId': groupeId,
      'geometrie': geometrie,
      'distancePlanM': distancePlanM,
      'dureePlanMin': dureePlanMin,
    });
    if (echecDemarrer != null) throw echecDemarrer!;
    trajetActif = Trajet(
      id: 900,
      busId: busId,
      sens: sens,
      groupeId: groupeId,
      heureDebut: DateTime(2026, 8, 20, 7, 30).toIso8601String(),
    );
    return trajetActif!;
  }

  @override
  Future<Trajet> terminerTrajet(int trajetId) async {
    if (echecTerminer != null) throw echecTerminer!;
    final t = trajetActif;
    trajetActif = null;
    return Trajet(id: trajetId, busId: t?.busId, statut: 'TERMINE');
  }

  @override
  Future<TrajetRoute?> getTrajetRoute(int busId) async {
    final t = trajetActif;
    if (t == null) return null;
    return TrajetRoute(
      trajetId: t.id,
      busId: busId,
      sens: t.sens,
      geometrie: tournee.geometrie,
      distancePlanM: tournee.distanceM,
      dureePlanMin: tournee.dureeMin,
    );
  }

  @override
  Future<TourneePlan> getTournee(int groupeId, String sens) async {
    if (tourneeEnAttente != null) await tourneeEnAttente;
    if (echecTournee != null) throw echecTournee!;
    return tournee;
  }

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
  }) async => EtaResult(etaMinutes: 12, modeEta: 'modele_direct');

  @override
  Future<GpsPosition?> getDernierePositionBus(int busId) async => null;

  @override
  Future<void> publierPosition({
    required int busId,
    required double latitude,
    required double longitude,
    double? vitesse,
    double? cap,
    double? precision,
  }) async {
    positions.add({
      'busId': busId,
      'latitude': latitude,
      'longitude': longitude,
      'vitesse': vitesse,
      'cap': cap,
    });
  }

  @override
  Future<List<Incident>> getIncidentsParBus(int busId) async => incidents;

  @override
  Future<Incident> creerIncident({
    required String type,
    required int busId,
    String? description,
    double? latitude,
    double? longitude,
  }) async {
    if (echecIncident != null) throw echecIncident!;
    incidentsCrees.add({
      'type': type,
      'busId': busId,
      'description': description,
      'latitude': latitude,
      'longitude': longitude,
    });
    final inc = Incident(
      id: incidents.length + 1,
      type: type,
      busId: busId,
      description: description,
      latitude: latitude,
      longitude: longitude,
      dateSignalement: DateTime(2026, 8, 20, 8).toIso8601String(),
    );
    incidents = [inc, ...incidents];
    return inc;
  }

  @override
  Future<List<MessageItem>> getMaConversation() async => conversation;

  @override
  Future<MessageItem> envoyerMessage(String contenu) async {
    if (echecMessage != null) throw echecMessage!;
    messagesEnvoyes.add(contenu);
    final m = MessageItem(
      id: conversation.length + 1,
      expediteurRole: 'CHAUFFEUR',
      contenu: contenu,
      dateEnvoi: DateTime(2026, 8, 20, 8).toIso8601String(),
    );
    conversation = [...conversation, m];
    return m;
  }

  @override
  Future<int> diffuserAuxParents(int busId, String contenu) async {
    if (echecDiffusion != null) throw echecDiffusion!;
    diffusions.add({'busId': busId, 'contenu': contenu});
    return 12;
  }

  @override
  Future<int> getUnreadCount() async {
    if (echecUnread != null) throw echecUnread!;
    return unread;
  }

  @override
  Future<List<NotificationItem>> getMesNotifications() async => notifications;
}
