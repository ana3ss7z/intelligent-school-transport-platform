export type Role = "ADMIN" | "CHAUFFEUR" | "PARENT";

export interface AuthResponse {
  token: string;
  userId: number;
  nom: string;
  email: string;
  role: Role;
}

export interface Eleve {
  id: number;
  nom: string;
  prenom: string;
  latitude: number;
  longitude: number;
  parentId: number | null;
  groupeId: number | null;
  busId: number | null;
  statutPresence: boolean;
  ordrePassage: number | null;
}

export interface Bus {
  id: number;
  matricule: string;
  capacite: number;
  statut: "ACTIF" | "INACTIF" | "EN_PANNE";
  chauffeurId: number | null;
  latitude: number | null;
  longitude: number | null;
}

export interface NotificationItem {
  id: number;
  type: string;
  statutEnvoi: "EN_ATTENTE" | "ENVOYE" | "ECHEC";
  parentId: number | null;
  titre: string;
  message: string;
  sourceId: number | null;
  sourceType: string | null;
  dateEnvoi: string;
}

export interface NotifStats {
  total: number;
  envoyes: number;
  echecs: number;
  attente: number;
  /** Compté en base : la console ne reçoit plus qu'une page et ne peut plus le dériver. */
  alertesAdmin: number;
}

/** Enveloppe de pagination renvoyée par les listes paginées côté serveur (MS4). */
export interface PageResponse<T> {
  content: T[];
  page: number;
  size: number;
  total: number;
  totalPages: number;
}

export interface QualityVerdict {
  niveau: "OK" | "DEGRADE" | "CRITIQUE";
  ok: boolean;
  raisons: string[];
  mesures?: Record<string, unknown>;
  plancher_silhouette?: number;
}

export interface ProductionResult {
  methode: string;
  k: number;
  silhouette: number | null;
  nb_eleves: number;
  distance: string;
  capacity: number;
  rayon_max_m: number;
  n_disperses: number;
  n_non_affectes: number;
  metrics: Record<string, number | null>;
  quality: QualityVerdict;
  bus_binding?: { n_lies: number; n_bus_actifs: number; k: number; manque_bus: number } | string;
  distribution: Record<string, number>;
  assignments?: Record<string, number>; // {eleveId: groupe} — prévisualisation carte
  groupes_appliques?: string | number;   // "non demandé" si simulation, sinon nb écrits
}

export interface LiveAnomaly {
  busId: number;
  type: string;
  timestamp: string;
  niveau?: string;
  [k: string]: unknown;
}

export interface GpsPosition {
  cibleType: "BUS" | "ELEVE";
  cibleId: number;
  latitude: number;
  longitude: number;
  vitesse?: number;
  cap?: number;
  horodatage?: string;
}

export type TypeIncident = "ACCIDENT" | "PANNE" | "RETARD" | "ABSENCE_CHAUFFEUR" | "ROUTE_BLOQUEE" | "AUTRE";
export type StatutIncident = "SIGNALE" | "CONFIRME" | "EN_TRAITEMENT" | "RESOLU";

export interface Incident {
  id: number;
  type: TypeIncident;
  statut: StatutIncident;
  busId: number | null;
  signalePar: number | null;
  description: string | null;
  latitude: number | null;
  longitude: number | null;
  dateSignalement: string;
  dateResolution: string | null;
  notesResolution: string | null;
}

export type SensTrajet = "MATIN" | "SOIR";
export type StatutTrajet = "EN_COURS" | "TERMINE";
export interface Trajet {
  id: number;
  busId: number;
  matricule: string;
  chauffeurId: number;
  sens: SensTrajet;
  statut: StatutTrajet;
  heureDebut: string;
  heureFin: string | null;
  groupeId?: number | null;
}

export interface IncidentInput {
  type: TypeIncident;
  busId: number;
  description?: string;
  latitude?: number;
  longitude?: number;
}

export interface IncidentStats {
  total?: number;
  signale?: number;
  confirme?: number;
  en_traitement?: number;
  resolu?: number;
  [k: string]: number | undefined;
}

export interface User {
  id: number;
  nom: string;
  email: string;
  role: Role;
  telephone: string | null;
}

export interface UserInput {
  nom: string;
  email: string;
  role: Role;
  telephone?: string | null;
  motDePasse?: string;
}

export interface Message {
  id: number;
  conversationChauffeurId: number;
  expediteurId: number;
  expediteurNom: string | null;
  expediteurRole: Role;
  destinataireId: number | null;
  destinataireRole: Role;
  contenu: string;
  lu: boolean;
  dateEnvoi: string;
}

export interface Conversation {
  chauffeurId: number;
  chauffeurNom: string | null;
  dernierMessage: string;
  dateDernier: string;
  nonLus: number;
}

export interface EleveInput {
  nom: string;
  prenom: string;
  latitude: number;
  longitude: number;
  parentId?: number | null;
  busId?: number | null;
  groupeId?: number | null;
  ordrePassage?: number | null;
}
