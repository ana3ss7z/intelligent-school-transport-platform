import { api } from "./client";
import type {
  AuthResponse, Bus, Conversation, Eleve, EleveInput, Incident, IncidentStats, LiveAnomaly,
  IncidentInput, Message, NotifStats, NotificationItem, PageResponse, ProductionResult, StatutIncident,
  Trajet, SensTrajet, User, UserInput,
} from "./types";

// Endpoints lourds (OSRM + clustering) : le timeout global de 20 s ne suffit pas.
const LONG = { timeout: 120000 };

// ── Auth (MS7) ───────────────────────────────────────────────
export const login = (email: string, motDePasse: string) =>
  api.post<AuthResponse>("/api/auth/login", { email, motDePasse }).then((r) => r.data);

// ── Élèves (MS2) ─────────────────────────────────────────────
export const getEleves = () => api.get<Eleve[]>("/api/eleves").then((r) => r.data);
export const getElevesParBus = (busId: number) =>
  api.get<Eleve[]>(`/api/eleves/bus/${busId}`).then((r) => r.data); // ordonné par ordrePassage
export const getElevesParParent = (parentId: number) =>
  api.get<Eleve[]>(`/api/eleves/parent/${parentId}`).then((r) => r.data);
export const setPresence = (id: number, present: boolean) =>
  api.patch(`/api/eleves/${id}/presence?present=${present}`).then((r) => r.data);

// ── Bus (MS1) ────────────────────────────────────────────────
export const getBusActifs = () => api.get<Bus[]>("/api/bus/actifs").then((r) => r.data);
export const getBus = () => api.get<Bus[]>("/api/bus").then((r) => r.data);
export const createBus = (p: { matricule: string; capacite: number; statut?: string; chauffeurId?: number | null }) =>
  api.post<Bus>("/api/bus", p).then((r) => r.data);
export const setBusStatut = (id: number, statut: string) =>
  api.patch(`/api/bus/${id}/statut?statut=${statut}`).then((r) => r.data);
export const deleteBus = (id: number) => api.delete(`/api/bus/${id}`).then((r) => r.data);
export const assignEleveBus = (id: number, busId: number) =>
  api.patch(`/api/eleves/${id}/bus?busId=${busId}`).then((r) => r.data);
export const updateBus = (id: number, p: { matricule: string; capacite: number; statut?: string; chauffeurId?: number | null }) =>
  api.put<Bus>(`/api/bus/${id}`, p).then((r) => r.data);
export const createEleve = (p: EleveInput) => api.post<Eleve>("/api/eleves", p).then((r) => r.data);
export const updateEleve = (id: number, p: EleveInput) => api.put<Eleve>(`/api/eleves/${id}`, p).then((r) => r.data);
export const deleteEleve = (id: number) => api.delete(`/api/eleves/${id}`).then((r) => r.data);

// ── Incidents (MS10) ─────────────────────────────────────────
export const getIncidents = () => api.get<Incident[]>("/api/incidents").then((r) => r.data);
export const getIncidentsByBus = (busId: number) => api.get<Incident[]>(`/api/incidents/bus/${busId}`).then((r) => r.data);
export const createIncident = (p: IncidentInput) => api.post<Incident>("/api/incidents", p).then((r) => r.data);
export const getIncidentStats = () => api.get<IncidentStats>("/api/incidents/stats").then((r) => r.data);
export const changeIncidentStatut = (id: number, statut: StatutIncident, notesResolution?: string) =>
  api.patch<Incident>(`/api/incidents/${id}/statut`, { statut, notesResolution }).then((r) => r.data);
export const deleteIncident = (id: number) => api.delete(`/api/incidents/${id}`).then((r) => r.data);

// ── Trajets (MS1) ────────────────────────────────────────────
// geometrie [[lat,lng],…] = tournée planifiée figée au démarrage (référence de déviation MS11)
export const demarrerTrajet = (
  busId: number, sens: SensTrajet, groupeId?: number | null, geometrie?: [number, number][],
  // Totaux OSRM de la tournée : figés avec elle pour que TOUS les fronts (y compris parent)
  // dérivent la même vitesse de circuit → ETA « distance restante » cohérente.
  totaux?: { distancePlanM?: number | null; dureePlanMin?: number | null },
) =>
  api.post<Trajet>("/api/trajets/demarrer", { busId, sens, groupeId, geometrie, ...totaux }).then((r) => r.data);
export const terminerTrajet = (id: number) =>
  api.post<Trajet>(`/api/trajets/${id}/terminer`).then((r) => r.data);
export const getMonTrajetActif = () =>
  api.get<Trajet | "">("/api/trajets/mon-actif").then((r) => (r.status === 204 ? null : r.data) as Trajet | null);
export const getTrajetsActifs = () => api.get<Trajet[]>("/api/trajets/actifs").then((r) => r.data);
export const getMesTrajets = () => api.get<Trajet[]>("/api/trajets/mes-trajets").then((r) => r.data);
export const getTrajetActifBus = (busId: number) =>
  api.get<Trajet | "">(`/api/trajets/bus/${busId}/actif`).then((r) => (r.status === 204 ? null : r.data) as Trajet | null);

/** Tournée figée du trajet en cours — pour l'ETA « distance restante le long du circuit ». */
export interface TrajetRoute {
  trajetId: number; busId: number; groupeId: number | null; sens: SensTrajet;
  geometrie: [number, number][]; distancePlanM: number | null; dureePlanMin: number | null;
}
export const getTrajetRoute = (busId: number) =>
  api.get<TrajetRoute | "">(`/api/trajets/bus/${busId}/route`)
    .then((r) => (r.status === 204 ? null : r.data) as TrajetRoute | null);

// ── GPS (MS3) ────────────────────────────────────────────────
export const getPositionsBus = () =>
  api.get("/api/gps/positions/bus").then((r) => r.data).catch(() => []);

// ── Clustering (MS6) ─────────────────────────────────────────
export const getDiagnostics = () => api.get("/api/clustering/diagnostics").then((r) => r.data);
export const getQuality = () => api.get("/api/clustering/quality").then((r) => r.data);
export const runProduction = (p: { capacity?: number; rayon?: number; appliquer?: boolean }) => {
  const q = new URLSearchParams();
  if (p.capacity != null) q.set("capacity", String(p.capacity));
  if (p.rayon != null) q.set("rayon", String(p.rayon));
  q.set("appliquer", String(p.appliquer ?? false));
  return api.post<ProductionResult>(`/api/clustering/production?${q}`, undefined, LONG).then((r) => r.data);
};
export interface ParetoRow { k: number; silhouette: number | null; compacite_med_m?: number; compacite_max_m?: number; faisable?: boolean }
export interface ParetoResult { k_retenu: number; capacity: number; pareto: ParetoRow[] }
export const getPareto = (capacity?: number) => {
  const q = new URLSearchParams();
  if (capacity != null) q.set("capacity", String(capacity));
  return api.post<ParetoResult>(`/api/clustering/pareto?${q}`, undefined, LONG).then((r) => r.data);
};

// ── Planification / VRP (MS5) ────────────────────────────────
export const getTournee = (groupeId: number, sens: "matin" | "soir" = "matin") =>
  api.post(`/api/planification/tournee?groupeId=${groupeId}&sens=${sens}`, undefined, LONG).then((r) => r.data);
/**
 * Étapes de tournée des enfants du parent connecté (portée imposée par le JWT côté MS5 —
 * les tournées complètes restent interdites au rôle PARENT : elles contiennent les domiciles
 * de toutes les familles du bus).
 */
export interface EtapeEnfant {
  eleveId: number; prenom: string; nom: string; groupeId: number | null; busId: number | null;
  rang: number; n_arrets: number;
  cumul_distance_m: number; cumul_duree_s: number;
  tournee_duree_min: number; tournee_distance_m: number;
}
export const getEtaMesEnfants = (sens: "matin" | "soir" = "matin") =>
  api.post<{ sens: string; enfants: EtapeEnfant[] }>(
    `/api/planification/mes-enfants?sens=${sens}`, undefined, LONG).then((r) => r.data);

export const getTournees = (sens: "matin" | "soir" = "matin") =>
  api.post(`/api/planification/tournees?sens=${sens}&persister=true`, undefined, LONG).then((r) => r.data);

// ── Notifications (MS4) ──────────────────────────────────────
/**
 * Journal d'administration, paginé côté serveur.
 *
 * <p>Auparavant sans paramètres : MS4 renvoyait la table entière (plus de 10 000 lignes) à
 * chaque sondage, pour 25 lignes affichées. Le journal grossit de plus de mille lignes par
 * minute pendant une simulation, donc la charge n'était pas stable.
 */
export const getNotifications = (params: {
  page?: number; size?: number; tri?: string; sens?: "asc" | "desc"; adminSeulement?: boolean;
} = {}) =>
  api
    .get<PageResponse<NotificationItem>>("/api/notifications", { params })
    .then((r) => r.data);
export const getNotifStats = () => api.get<NotifStats>("/api/notifications/stats").then((r) => r.data);
export const getMesNotifications = () =>
  api.get<NotificationItem[]>("/api/notifications/mes-notifications").then((r) => r.data);

// ── Messagerie (MS4) — chauffeur ↔ administration ────────────
export const sendMessage = (p: { destinataireId?: number; contenu: string }) =>
  api.post<Message>("/api/messages", p).then((r) => r.data);
export const getMaConversation = () =>
  api.get<Message[]>("/api/messages/ma-conversation").then((r) => r.data);
export const getConversationsAdmin = () =>
  api.get<Conversation[]>("/api/messages/conversations").then((r) => r.data);
export const getConversation = (chauffeurId: number) =>
  api.get<Message[]>(`/api/messages/conversation/${chauffeurId}`).then((r) => r.data);
export const getUnreadMessages = () =>
  api.get<{ count: number }>("/api/messages/non-lus").then((r) => r.data.count);
export const diffuserParents = (busId: number, contenu: string) =>
  api.post<{ parents: number }>(`/api/messages/diffusion?busId=${busId}`, { contenu }).then((r) => r.data);
export const getParentInbox = () =>
  api.get<Message[]>("/api/messages/parent").then((r) => r.data);

// ── Assistant LLM (MS9) ──────────────────────────────────────
export interface ChatTurn { role: "user" | "assistant"; content: string }
export interface ChatReply { reply: string; used_tools?: string[]; degraded?: boolean }
export const chatLLM = (message: string, history: ChatTurn[] = []) =>
  api.post<ChatReply>("/api/llm/chat", { message, history }, LONG).then((r) => r.data);

export interface AdminQueryReply {
  reply: string;
  sql: string | null;
  colonnes: string[];
  lignes: unknown[][];
  tronque?: boolean;
  degraded?: boolean;
}
export const adminQuery = (question: string, history: ChatTurn[] = []) =>
  api.post<AdminQueryReply>("/api/llm/admin/query", { question, history }, LONG).then((r) => r.data);

// ── Analytique / anomalies (MS11) ────────────────────────────
export const getLiveAnomalies = (limit = 20) =>
  api.get<{ n: number; anomalies: LiveAnomaly[] }>(`/api/analytique/live?limit=${limit}`).then((r) => r.data);
export const getAnomalyModelInfo = () => api.get("/api/analytique/model-info").then((r) => r.data);
export const getAnomalyScan = (limit = 20) =>
  api.get(`/api/analytique/anomalies/scan?limit=${limit}`, LONG).then((r) => r.data);

// ── ETA (MS12) ───────────────────────────────────────────────
export const getEtaModelInfo = () => api.get("/api/eta/model-info").then((r) => r.data);
export interface EtaResult {
  eta_minutes: number;
  intervalle_min?: [number, number];
  heure_arrivee_estimee?: string;
  duree_base_min?: number;
}
export const predictEta = (p: {
  bus_lat?: number; bus_lng?: number; dest_lat?: number; dest_lng?: number;
  distance_routiere_m?: number; duree_base_s?: number; moment?: string; heure_depart?: number;
}) => api.post<EtaResult>("/api/eta/predict", { auto_context: true, ...p }, LONG).then((r) => r.data);

// ── Utilisateurs (MS7) ───────────────────────────────────────
export const getUsers = (role?: string) =>
  api.get<User[]>(`/api/auth/users${role ? `?role=${role}` : ""}`).then((r) => r.data);
export const createUser = (p: UserInput) => api.post<User>("/api/auth/users", p).then((r) => r.data);
export const updateUser = (id: number, p: UserInput) => api.put<User>(`/api/auth/users/${id}`, p).then((r) => r.data);
export const deleteUser = (id: number) => api.delete(`/api/auth/users/${id}`).then((r) => r.data);


// ── Paramètres (MS13) ────────────────────────────────────────
/** Un réglage servi par MS13. Les métadonnées viennent du catalogue serveur : aucun libellé en dur ici. */
export interface Parametre {
  cle: string;
  valeur: string;
  type: "NUMBER" | "BOOLEAN" | "STRING" | "ENUM" | "SECRET";
  groupe: string;
  ordre: number;
  libelle: string;
  description: string | null;
  unite: string | null;
  valeurDefaut: string;
  min: number | null;
  max: number | null;
  options: string | null;   // valeurs permises, séparées par des virgules (type ENUM)
  sensible: boolean;
  impact: "IMMEDIAT" | "PROCHAIN_CALCUL" | "PROCHAIN_TRAJET" | "REDEMARRAGE";
  modifie: boolean;
  /** Pour un secret : une valeur est-elle enregistrée ? (le masque ne permet pas de le déduire) */
  defini: boolean;
  /**
   * Condition d'activation : ce réglage n'a de sens que si le paramètre `dependDe` vaut
   * `dependValeur`. `null` quand le réglage est toujours actif.
   *
   * Le serveur accepte malgré tout l'écriture d'un champ dont la condition n'est pas remplie :
   * c'est une aide à la saisie, pas une règle de validation.
   */
  dependDe: string | null;
  dependValeur: string | null;
  dateModif: string | null;
  modifiePar: string | null;
}

export interface ParametreSchema {
  groupes: string[];
  parametres: Record<string, Parametre[]>;
  total: number;
}

/** Valeurs effectives, secrets masqués. Ouvert à tous les rôles (les 3 espaces en dépendent). */
export const getParametres = () => api.get<Parametre[]>("/api/parametres").then((r) => r.data);

/** Catalogue groupé par onglet (ADMIN) — construit le formulaire. */
export const getParametresSchema = () =>
  api.get<ParametreSchema>("/api/parametres/schema").then((r) => r.data);

/**
 * Écriture par lot (ADMIN). Le serveur valide TOUT avant d'écrire quoi que ce soit :
 * une seule valeur refusée annule l'enregistrement entier (400), ce qui évite un jeu de
 * seuils à moitié appliqué.
 *
 * Un champ secret laissé vide — ou contenant encore son masque — est ignoré côté serveur,
 * jamais écrit : réenregistrer un onglet ne détruit pas une clé API.
 */
export const updateParametres = (valeurs: Record<string, string>) =>
  api.put<{ modifiees: string[]; n: number; parametres: Parametre[] }>(
    "/api/parametres", { valeurs }).then((r) => r.data);

/** Retour aux défauts du catalogue. Sans argument : tout, sauf les secrets. */
export const resetParametres = (p?: { cle?: string; groupe?: string }) => {
  const q = new URLSearchParams();
  if (p?.cle) q.set("cle", p.cle);
  if (p?.groupe) q.set("groupe", p.groupe);
  return api.post<{ modifiees: string[]; n: number; parametres: Parametre[] }>(
    `/api/parametres/reset${q.toString() ? `?${q}` : ""}`).then((r) => r.data);
};

// ── Vérification des modèles LLM (MS9) ───────────────────────
export interface ModelesCheck {
  resultats: { fournisseur: string; statut: string; detail?: string; n_servis?: number;
               modeles: { modele: string; servi: boolean }[] }[];
  cascade: string[];
  modeles_absents: string[];
  verdict: "OK" | "MODELES_ABSENTS";
}
/** Demande à chaque fournisseur la liste de ses modèles servis et confronte la cascade configurée. */
export const verifierModelesLlm = () =>
  api.get<ModelesCheck>("/api/llm/admin/models-check", LONG).then((r) => r.data);
