// Modèles de données — miroirs des DTO backend (cf. web-admin/src/api/types.ts).

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

  MessageItem({
    required this.id,
    this.expediteurId,
    this.expediteurNom,
    this.expediteurRole,
    this.contenu = '',
    this.lu = false,
    this.dateEnvoi,
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

  EtaResult({required this.etaMinutes, this.heureArrivee});

  factory EtaResult.fromJson(Map<String, dynamic> j) => EtaResult(
    etaMinutes: (j['eta_minutes'] as num).toDouble(),
    heureArrivee: j['heure_arrivee_estimee'] as String?,
  );
}

/// Tour de conversation pour l'assistant LLM.
class ChatTurn {
  final String role; // user | assistant
  final String content;
  const ChatTurn(this.role, this.content);

  Map<String, dynamic> toJson() => {'role': role, 'content': content};
}

class ChatReply {
  final String reply;
  final List<String> usedTools;
  final bool degraded;

  ChatReply({
    required this.reply,
    this.usedTools = const [],
    this.degraded = false,
  });

  factory ChatReply.fromJson(Map<String, dynamic> j) => ChatReply(
    reply: (j['reply'] ?? '') as String,
    usedTools:
        (j['used_tools'] as List?)?.map((e) => e.toString()).toList() ??
        const [],
    degraded: (j['degraded'] ?? false) as bool,
  );
}
