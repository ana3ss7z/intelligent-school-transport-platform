import { useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";
import { usePolling } from "../hooks/usePolling";
import { getIncidents, getIncidentStats, changeIncidentStatut, deleteIncident } from "../api/endpoints";
import type { StatutIncident } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Panel, Stat, StatusChip, SectionTitle } from "../components/ui";
import { SkeletonStats, SkeletonTable } from "../components/Skeleton";
import { ErrorState, EmptyState } from "../components/AsyncState";

const STATUTS: StatutIncident[] = ["SIGNALE", "CONFIRME", "EN_TRAITEMENT", "RESOLU"];

const typeTone = (t: string) =>
  ["ACCIDENT", "PANNE", "ROUTE_BLOQUEE"].includes(t) ? "alert"
  : ["RETARD", "ABSENCE_CHAUFFEUR"].includes(t) ? "warn" : "route";
const statutTone = (s: string) =>
  s === "RESOLU" ? "ok" : s === "EN_TRAITEMENT" ? "line2" : s === "CONFIRME" ? "route" : "warn";

export function Incidents() {
  const { role } = useAuth();
  const isAdmin = role === "ADMIN";
  const toast = useToast();
  const { data, loading, error, refreshing, refetch } = usePolling(async () => {
    const [items, stats] = await Promise.all([getIncidents(), getIncidentStats().catch(() => null)]);
    return { items, stats };
  }, 15000);
  const [filtre, setFiltre] = useState<StatutIncident | "">("");

  const majStatut = async (id: number, statut: StatutIncident) => {
    let notes: string | undefined;
    if (statut === "RESOLU") {
      const n = window.prompt("Notes de résolution (optionnel) — les parents seront notifiés :", "");
      if (n === null) return; // annulé
      notes = n || undefined;
    }
    try {
      await changeIncidentStatut(id, statut, notes);
      toast.success(statut === "RESOLU" ? `Incident ${id} résolu — parents notifiés` : `Incident ${id} → ${statut}`);
      refetch();
    } catch (e: unknown) {
      toast.error((e as { message?: string })?.message ?? "Échec du changement de statut");
    }
  };

  const supprimer = async (id: number) => {
    if (!window.confirm(`Supprimer l'incident ${id} ?`)) return;
    try { await deleteIncident(id); toast.success(`Incident ${id} supprimé`); refetch(); }
    catch (e: unknown) { toast.error((e as { message?: string })?.message ?? "Échec de la suppression"); }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Incidents</h1><p className="text-ink-soft text-sm">Chargement…</p></div>
        <SkeletonStats /><Panel className="p-4"><SkeletonTable /></Panel>
      </div>
    );
  }
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;

  const items = [...data!.items].sort((a, b) => b.id - a.id);
  const rows = filtre ? items.filter((i) => i.statut === filtre) : items;
  const s = data!.stats;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Incidents</h1>
          <p className="text-ink-soft text-sm">Signalements du terrain — suivi et résolution (MS10).</p>
        </div>
        <RefreshCw size={14} className={`shrink-0 ${refreshing ? "animate-spin text-route" : "text-ink-soft"}`} />
      </div>

      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat label="Total" value={s?.total ?? items.length} tone="route" />
        <Stat label="Signalés" value={s?.signale ?? items.filter((i) => i.statut === "SIGNALE").length} tone="warn" />
        <Stat label="En traitement" value={s?.en_traitement ?? items.filter((i) => i.statut === "EN_TRAITEMENT").length} tone="line2" />
        <Stat label="Résolus" value={s?.resolu ?? items.filter((i) => i.statut === "RESOLU").length} tone="ok" />
      </div>

      <Panel className="p-4">
        <div className="flex items-center justify-between mb-3 gap-2">
          <SectionTitle sub={`${rows.length} entrées`}>Journal des incidents</SectionTitle>
          <select aria-label="Filtrer par statut" value={filtre} onChange={(e) => setFiltre(e.target.value as StatutIncident | "")}
            className="rounded-lg border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-route">
            <option value="">Tous les statuts</option>
            {STATUTS.map((st) => <option key={st} value={st}>{st}</option>)}
          </select>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line">
                <th className="py-2 pr-3">#</th><th className="py-2 pr-3">Type</th><th className="py-2 pr-3">Bus</th>
                <th className="py-2 pr-3">Description</th><th className="py-2 pr-3">Date</th>
                <th className="py-2 pr-3">Statut</th>{isAdmin && <th className="py-2 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((i) => (
                <tr key={i.id} className="border-b border-line/60">
                  <td className="py-2 pr-3 tabular text-ink-soft">{i.id}</td>
                  <td className="py-2 pr-3"><StatusChip tone={typeTone(i.type)}>{i.type}</StatusChip></td>
                  <td className="py-2 pr-3 tabular">{i.busId ?? "—"}</td>
                  <td className="py-2 pr-3 max-w-[320px] truncate" title={i.description ?? ""}>{i.description ?? "—"}</td>
                  <td className="py-2 pr-3 tabular text-ink-soft">{new Date(i.dateSignalement).toLocaleString("fr-FR")}</td>
                  <td className="py-2 pr-3">
                    {isAdmin ? (
                      <select value={i.statut} onChange={(e) => majStatut(i.id, e.target.value as StatutIncident)}
                        aria-label={`Statut de l'incident ${i.id}`}
                        className="rounded-md border border-line bg-panel px-1.5 py-1 text-xs outline-none focus:border-route">
                        {STATUTS.map((st) => <option key={st} value={st}>{st}</option>)}
                      </select>
                    ) : <StatusChip tone={statutTone(i.statut)}>{i.statut}</StatusChip>}
                  </td>
                  {isAdmin && (
                    <td className="py-2 text-right">
                      <button onClick={() => supprimer(i.id)} aria-label={`Supprimer l'incident ${i.id}`}
                        className="text-ink-soft hover:text-alert transition-colors p-1"><Trash2 size={15} /></button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <EmptyState message={filtre ? `Aucun incident « ${filtre} ».` : "Aucun incident signalé."} />}
        </div>
      </Panel>
    </div>
  );
}
