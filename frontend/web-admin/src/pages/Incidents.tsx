import { useState } from "react";
import { RefreshCw, Trash2, Download } from "lucide-react";
import { usePolling } from "../hooks/usePolling";
import { useTableView } from "../hooks/useTableView";
import { getIncidents, getIncidentStats, changeIncidentStatut, deleteIncident } from "../api/endpoints";
import type { Incident, StatutIncident } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { useConfirm } from "../components/ConfirmDialog";
import { Pager, SortTh } from "../components/Pager";
import { Panel, Stat, StatusChip, SectionTitle } from "../components/ui";
import { SkeletonStats, SkeletonTable } from "../components/Skeleton";
import { ErrorState, EmptyState } from "../components/AsyncState";
import { exportCsv } from "../lib/csv";

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
  const { confirm, prompt } = useConfirm();
  const { data, loading, error, refreshing, refetch } = usePolling(async () => {
    const [items, stats] = await Promise.all([getIncidents(), getIncidentStats().catch(() => null)]);
    return { items, stats };
  }, 15000);
  const [filtre, setFiltre] = useState<StatutIncident | "">("");

  const majStatut = async (id: number, statut: StatutIncident) => {
    let notes: string | undefined;
    if (statut === "RESOLU") {
      const n = await prompt({ title: "Résoudre l'incident", message: "Notes de résolution (optionnel) — les parents seront notifiés.", placeholder: "ex. dépannage effectué", confirmLabel: "Résoudre" });
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
    if (!await confirm({ title: "Supprimer l'incident", message: `Supprimer l'incident ${id} ?`, danger: true, confirmLabel: "Supprimer" })) return;
    try { await deleteIncident(id); toast.success(`Incident ${id} supprimé`); refetch(); }
    catch (e: unknown) { toast.error((e as { message?: string })?.message ?? "Échec de la suppression"); }
  };

  const items = [...(data?.items ?? [])].sort((a, b) => b.id - a.id);
  const rows = filtre ? items.filter((i) => i.statut === filtre) : items;
  const { pageRows, page, setPage, totalPages, total, sortKey, sortDir, toggleSort } =
    useTableView<Incident>(rows, { pageSize: 25, initialSort: "id", initialDir: "desc" });

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Incidents</h1><p className="text-ink-soft text-sm">Chargement…</p></div>
        <SkeletonStats /><Panel className="p-4"><SkeletonTable /></Panel>
      </div>
    );
  }
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;

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
          <SectionTitle sub={`${total} entrées`}>Journal des incidents</SectionTitle>
          <div className="flex items-center gap-2">
            <select aria-label="Filtrer par statut" value={filtre} onChange={(e) => setFiltre(e.target.value as StatutIncident | "")}
              className="rounded-lg border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-route">
              <option value="">Tous les statuts</option>
              {STATUTS.map((st) => <option key={st} value={st}>{st}</option>)}
            </select>
            <button onClick={() => exportCsv("incidents", rows as unknown as Record<string, unknown>[])}
              className="inline-flex items-center gap-1.5 text-sm text-ink-soft hover:text-ink transition-colors">
              <Download size={15} /> CSV
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line">
                <SortTh label="#" active={sortKey === "id"} dir={sortDir} onClick={() => toggleSort("id")} />
                <SortTh label="Type" active={sortKey === "type"} dir={sortDir} onClick={() => toggleSort("type")} />
                <SortTh label="Bus" active={sortKey === "busId"} dir={sortDir} onClick={() => toggleSort("busId")} />
                <th className="py-2 pr-3">Description</th>
                <SortTh label="Date" active={sortKey === "dateSignalement"} dir={sortDir} onClick={() => toggleSort("dateSignalement")} />
                <SortTh label="Statut" active={sortKey === "statut"} dir={sortDir} onClick={() => toggleSort("statut")} />
                {isAdmin && <th className="py-2 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((i) => (
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
          {total === 0 && <EmptyState message={filtre ? `Aucun incident « ${filtre} ».` : "Aucun incident signalé."} />}
          <Pager page={page} totalPages={totalPages} total={total} onPage={setPage} />
        </div>
      </Panel>
    </div>
  );
}
