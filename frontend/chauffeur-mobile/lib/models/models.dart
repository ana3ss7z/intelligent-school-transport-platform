// Modèles de données — miroirs des DTO backend (cf. web-app/src/api/types.ts).
//
// Rappel de casse : les MS Java (MS1/MS2/MS4/MS10) répondent en camelCase,
// les MS Python (MS5 planification, MS12 ETA) en snake_case.

double? _toD(dynamic v) => v == null ? null : (v as num).toDouble();
int? _toI(dynamic v) => v == null ? null : (v as num).toInt();

/// Utilisateur connecté (réponse de POST /api/auth/login).
class AuthUser {
  final String token;
  final int userId;
  final String nom;
  final String email;
  final String role; // ADMIN | CHAUFFEUR | PARENT

  AuthUser({
    required this.token,
    required this.userId,
    required this.nom,
    required this.email,
    required this.role,
  });

  factory AuthUser.fromJson(Map<String, dynamic> j) => AuthUser(
    token: j['token'] as String,
    userId: (j['userId'] as num).toInt(),
    nom: (j['nom'] ?? '') as String,
    email: (j['email'] ?? '') as String,
    role: (j['role'] ?? '') as String,
  );

  Map<String, dynamic> toJson() => {
    'token': token,
    'userId': userId,
    'nom': nom,
    'email': email,
    'role': role,
  };
}

class Eleve {
  final int id;
  final String nom;
  final String prenom;
  final double? latitude;
  final double? longitude;
  final int? parentId;
  final int? groupeId;
  final int? busId;
  final bool statutPresence;
  final int? ordrePassage;

  Eleve({
    required this.id,
    required this.nom,
    required this.prenom,
    this.latitude,
    this.longitude,
    this.parentId,
    this.groupeId,
    this.busId,
    this.statutPresence = false,
    this.ordrePassage,
  });

  String get nomComplet => '$prenom $nom'.trim();

  Eleve copyWith({bool? statutPresence}) => Eleve(
    id: id,
    nom: nom,
    prenom: prenom,
    latitude: latitude,
    longitude: longitude,
    parentId: parentId,
    groupeId: groupeId,
    busId: busId,
    statutPresence: statutPresence ?? this.statutPresence,
    ordrePassage: ordrePassage,
  );

  factory Eleve.fromJson(Map<String, dynamic> j) => Eleve(
    id: (j['id'] as num).toInt(),
    nom: (j['nom'] ?? '') as String,
    prenom: (j['prenom'] ?? '') as String,
    latitude: _toD(j['latitude']),
    longitude: _toD(j['longitude']),
    parentId: _toI(j['parentId']),
    groupeId: _toI(j['groupeId']),
    busId: _toI(j['busId']),
    statutPresence: (j['statutPresence'] ?? false) as bool,
    ordrePassage: _toI(j['ordrePassage']),
  );
}

class Bus {
  final int id;
  final String matricule;
  final int? capacite;
  final String statut; // ACTIF | INACTIF | EN_PANNE
  final int? chauffeurId;
  final double? latitude;
  final double? longitude;

  Bus({
    required this.id,
    required this.matricule,
    this.capacite,
    this.statut = 'INACTIF',
    this.chauffeurId,
    this.latitude,
    this.longitude,
  });

  factory Bus.fromJson(Map<String, dynamic> j) => Bus(
    id: (j['id'] as num).toInt(),
    matricule: (j['matricule'] ?? '') as String,
    capacite: _toI(j['capacite']),
    statut: (j['statut'] ?? 'INACTIF') as String,
    chauffeurId: _toI(j['chauffeurId']),
    latitude: _toD(j['latitude']),
    longitude: _toD(j['longitude']),
  );
}

class Trajet {
  final int id;
  final int? busId;
  final String? matricule;
  final int? chauffeurId;
  final String sens; // MATIN | SOIR
  final String statut; // EN_COURS | TERMINE
  final String? heureDebut;
  final String? heureFin;
  final int? groupeId;

  Trajet({
    required this.id,
    this.busId,
    this.matricule,
    this.chauffeurId,
    this.sens = 'MATIN',
    this.statut = 'EN_COURS',
    this.heureDebut,
    this.heureFin,
    this.groupeId,
  });

  bool get isSoir => sens.toUpperCase() == 'SOIR';

  /// Sens en minuscules — c'est la forme attendue par MS5 et MS12.
  String get sensBas => isSoir ? 'soir' : 'matin';

  factory Trajet.fromJson(Map<String, dynamic> j) => Trajet(
    id: (j['id'] as num).toInt(),
    busId: _toI(j['busId']),
    matricule: j['matricule'] as String?,
    chauffeurId: _toI(j['chauffeurId']),
    sens: (j['sens'] ?? 'MATIN') as String,
    statut: (j['statut'] ?? 'EN_COURS') as String,
    heureDebut: j['heureDebut']?.toString(),
    heureFin: j['heureFin']?.toString(),
    groupeId: _toI(j['groupeId']),
  );
}

/// Étape d'un élève dans la tournée optimisée (bloc `etapes` de MS5 `/tournee`).
///
/// Le cumul est mesuré **depuis l'école le long du circuit** — c'est lui qu'on
/// passe à MS12 comme distance/durée de base, et non une distance à vol d'oiseau.
class EtapeTournee {
  final int eleveId;
  final int rang;
  final double cumulDureeS;
  final double cumulDistanceM;

  const EtapeTournee({
    required this.eleveId,
    required this.rang,
    required this.cumulDureeS,
    required this.cumulDistanceM,
  });

  factory EtapeTournee.fromJson(Map<String, dynamic> j) => EtapeTournee(
    eleveId: (j['eleveId'] as num).toInt(),
    rang: (j['rang'] as num).toInt(),
    cumulDureeS: _toD(j['cumul_duree_s']) ?? 0,
    cumulDistanceM: _toD(j['cumul_distance_m']) ?? 0,
  );
}

/// Tournée planifiée d'un groupe (MS5 `POST /api/planification/tournee`).
///
/// C'est l'objet qu'on fige au démarrage d'un trajet : `geometrie` devient la
/// **référence de déviation de MS11**, `distanceM`/`dureeMin` donnent la vitesse
/// moyenne réelle du circuit pour l'ETA restant.
class TourneePlan {
  final String sens; // matin | soir
  final List<int> ordre; // ids d'élèves, dans l'ordre de passage
  final List<EtapeTournee> etapes;
  final List<List<double>> geometrie; // [[lat, lng], …]
  final double? distanceM;
  final double? dureeMin;
  final double? gainPct;

  const TourneePlan({
    this.sens = 'matin',
    this.ordre = const [],
    this.etapes = const [],
    this.geometrie = const [],
    this.distanceM,
    this.dureeMin,
    this.gainPct,
  });

  bool get hasGeometrie => geometrie.length >= 2;

  factory TourneePlan.fromJson(Map<String, dynamic> j) => TourneePlan(
    sens: (j['sens'] ?? 'matin') as String,
    ordre: ((j['ordre'] as List?) ?? const [])
        .map((e) => (e as num).toInt())
        .toList(),
    etapes: ((j['etapes'] as List?) ?? const [])
        .map((e) => EtapeTournee.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList(),
    geometrie: ((j['geometrie'] as List?) ?? const [])
        .map((p) => (p as List).map((c) => (c as num).toDouble()).toList())
        .where((p) => p.length >= 2)
        .toList(),
    distanceM: _toD(j['distance_m']),
    dureeMin: _toD(j['duree_min']),
    gainPct: _toD(j['gain_vs_baseline_%']),
  );

  /// Sérialisation locale (cache `shared_preferences`) — pas un DTO backend.
  Map<String, dynamic> toJson() => {
    'sens': sens,
    'ordre': ordre,
    'etapes': [
      for (final e in etapes)
        {
          'eleveId': e.eleveId,
          'rang': e.rang,
          'cumul_duree_s': e.cumulDureeS,
          'cumul_distance_m': e.cumulDistanceM,
        },
    ],
    'geometrie': geometrie,
    'distance_m': distanceM,
    'duree_min': dureeMin,
    'gain_vs_baseline_%': gainPct,
  };
}

/// Tournée figée du trajet en cours (MS1 `/api/trajets/bus/{id}/route`).
class TrajetRoute {
  final int trajetId;
  final int? busId;
  final String sens;
  final List<List<double>> geometrie;
  final double? distancePlanM;
  final double? dureePlanMin;

  TrajetRoute({
    required this.trajetId,
    this.busId,
    this.sens = 'MATIN',
    this.geometrie = const [],
    this.distancePlanM,
    this.dureePlanMin,
  });

  bool get hasGeometrie => geometrie.length >= 2;

  factory TrajetRoute.fromJson(Map<String, dynamic> j) => TrajetRoute(
    trajetId: (j['trajetId'] as num).toInt(),
    busId: _toI(j['busId']),
    sens: (j['sens'] ?? 'MATIN') as String,
    geometrie: ((j['geometrie'] as List?) ?? const [])
        .map((p) => (p as List).map((c) => (c as num).toDouble()).toList())
        .where((p) => p.length >= 2)
        .toList(),
    distancePlanM: _toD(j['distancePlanM']),
    dureePlanMin: _toD(j['dureePlanMin']),
  );
}

class GpsPosition {
  final int? id;
  final String cibleType; // BUS | ELEVE
  final int cibleId;
  final double latitude;
  final double longitude;
  final double? vitesse;
  final double? cap;
  final String? horodatage;

  GpsPosition({
    this.id,
    required this.cibleType,
    required this.cibleId,
    required this.latitude,
    required this.longitude,
    this.vitesse,
    this.cap,
    this.horodatage,
  });

  factory GpsPosition.fromJson(Map<String, dynamic> j) => GpsPosition(
    id: _toI(j['id']),
    cibleType: (j['cibleType'] ?? '') as String,
    cibleId: (j['cibleId'] as num).toInt(),
    latitude: (j['latitude'] as num).toDouble(),
    longitude: (j['longitude'] as num).toDouble(),
    vitesse: _toD(j['vitesse']),
    cap: _toD(j['cap']),
    horodatage: j['horodatage']?.toString(),
  );
}

/// Types d'incident acceptés par MS10 (enum `TypeIncident`).
const kTypesIncident = <String>[
  'PANNE',
  'ACCIDENT',
  'RETARD',
  'ROUTE_BLOQUEE',
  'ABSENCE_CHAUFFEUR',
  'AUTRE',
];

class Incident {
  final int id;
  final String type;
  final String statut; // SIGNALE | CONFIRME | EN_TRAITEMENT | RESOLU
  final int? busId;
  final int? signalePar;
  final String? description;
  final double? latitude;
  final double? longitude;
  final String? dateSignalement;
  final String? dateResolution;
  final String? notesResolution;

  Incident({
    required this.id,
    required this.type,
    this.statut = 'SIGNALE',
    this.busId,
    this.signalePar,
    this.description,
    this.latitude,
    this.longitude,
    this.dateSignalement,
    this.dateResolution,
    this.notesResolution,
  });

  factory Incident.fromJson(Map<String, dynamic> j) => Incident(
    id: (j['id'] as num).toInt(),
    type: (j['type'] ?? 'AUTRE') as String,
    statut: (j['statut'] ?? 'SIGNALE') as String,
    busId: _toI(j['busId']),
    signalePar: _toI(j['signalePar']),
    description: j['description'] as String?,
    latitude: _toD(j['latitude']),
    longitude: _toD(j['longitude']),
    dateSignalement: j['dateSignalement']?.toString(),
    dateResolution: j['dateResolution']?.toString(),
    notesResolution: j['notesResolution'] as String?,
  );
}

class NotificationItem {
  final int id;
  final String type;
  final String? statutEnvoi;
  final String? titre;
  final String? message;
  final int? sourceId;
  final String? sourceType;
  final String? dateEnvoi;

  NotificationItem({
    required this.id,
    required this.type,
    this.statutEnvoi,
    this.titre,
    this.message,
    this.sourceId,
    this.sourceType,
    this.dateEnvoi,
  });

  factory NotificationItem.fromJson(Map<String, dynamic> j) => NotificationItem(
    id: (j['id'] as num).toInt(),
    type: (j['type'] ?? '') as String,
    statutEnvoi: j['statutEnvoi'] as String?,
    titre: j['titre'] as String?,
    message: j['message'] as String?,
    sourceId: _toI(j['sourceId']),
    sourceType: j['sourceType'] as String?,
    dateEnvoi: j['dateEnvoi']?.toString(),
  );
}

class MessageItem {
  final int id;
  final int? expediteurId;
  final String? expediteurNom;
  final String? expediteurRole;
  final String contenu;
  final bool lu;
  final String? dateEnvoi;

  /// Message local pas encore confirmé par le serveur (mise à jour optimiste).
  /// Ces deux champs ne viennent jamais du backend.
  final bool enAttente;
  final bool echec;

  MessageItem({
    required this.id,
    this.expediteurId,
    this.expediteurNom,
    this.expediteurRole,
    this.contenu = '',
    this.lu = false,
    this.dateEnvoi,
    this.enAttente = false,
    this.echec = false,
  });

  factory MessageItem.fromJson(Map<String, dynamic> j) => MessageItem(
    id: (j['id'] as num).toInt(),
    expediteurId: _toI(j['expediteurId']),
    expediteurNom: j['expediteurNom'] as String?,
    expediteurRole: j['expediteurRole'] as String?,
    contenu: (j['contenu'] ?? '') as String,
    lu: (j['lu'] ?? false) as bool,
    dateEnvoi: j['dateEnvoi']?.toString(),
  );
}

/// Réponse de POST /api/eta/predict (on lit surtout eta_minutes).
class EtaResult {
  final double etaMinutes;
  final String? heureArrivee;

  /// `modele_direct` | `facteur_contexte` — MS12 signale ici s'il a dû sortir
  /// du domaine d'entraînement (tronçons 0,7–4 km) et appliquer sa garde.
  final String? modeEta;

  EtaResult({required this.etaMinutes, this.heureArrivee, this.modeEta});

  factory EtaResult.fromJson(Map<String, dynamic> j) => EtaResult(
    etaMinutes: (j['eta_minutes'] as num).toDouble(),
    heureArrivee: j['heure_arrivee_estimee'] as String?,
    modeEta: j['mode_eta'] as String?,
  );
}
