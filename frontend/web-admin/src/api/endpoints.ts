import { api } from "./client";
import type {
  AuthResponse, Bus, Conversation, Eleve, EleveInput, Incident, IncidentStats, LiveAnomaly,
  IncidentInput, Message, NotifStats, NotificationItem, ProductionResult, StatutIncident,
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
export const demarrerTrajet = (busId: number, sens: SensTrajet, groupeId?: number | null, geometrie?: [number, number][]) =>
  api.post<Trajet>("/api/trajets/demarrer", { busId, sens, groupeId, geometrie }).then((r) => r.data);
export const terminerTrajet = (id: number) =>
  api.post<Trajet>(`/api/trajets/${id}/terminer`).then((r) => r.data);
export const getMonTrajetActif = () =>
  api.get<Trajet | "">("/api/trajets/mon-actif").then((r) => (r.status === 204 ? null : r.data) as Trajet | null);
export const getTrajetsActifs = () => api.get<Trajet[]>("/api/trajets/actifs").then((r) => r.data);
export const getMesTrajets = () => api.get<Trajet[]>("/api/trajets/mes-trajets").then((r) => r.data);
export const getTrajetActifBus = (busId: number) =>
  api.get<Trajet | "">(`/api/trajets/bus/${busId}/actif`).then((r) => (r.status === 204 ? null : r.data) as Trajet | null);

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
export const getTournees = (sens: "matin" | "soir" = "matin") =>
  api.post(`/api/planification/tournees?sens=${sens}&persister=true`, undefined, LONG).then((r) => r.data);

// ── Notifications (MS4) ──────────────────────────────────────
export const getNotifications = () =>
  api.get<NotificationItem[]>("/api/notifications").then((r) => r.data);
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

