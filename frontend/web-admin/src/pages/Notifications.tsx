import { useState } from "react";
import { RefreshCw, Download } from "lucide-react";
import { usePolling } from "../hooks/usePolling";
import { useTableView } from "../hooks/useTableView";
import { getNotifications, getNotifStats } from "../api/endpoints";
import type { NotificationItem } from "../api/types";
import { Panel, Stat, StatusChip, SectionTitle } from "../components/ui";
import { Pager, SortTh } from "../components/Pager";
import { SkeletonStats, SkeletonTable } from "../components/Skeleton";
import { ErrorState, EmptyState } from "../components/AsyncState";
import { exportCsv } from "../lib/csv";
import { useParams } from "../params/ParamsContext";

const ADMIN_TYPES = ["ALERTE_QUALITE", "ANOMALIE_DETECTEE"];
const typeTone = (t: string) =>
  t.startsWith("INCIDENT") || t === "ANOMALIE_DETECTEE" ? "alert"
  : t === "ALERTE_QUALITE" || t === "RETARD" ? "warn"
  : t === "ENFANT_A_BORD" || t === "BUS_ARRIVE_ECOLE" ? "ok" : "route";
const envoiTone = (s: string) => (s === "ENVOYE" ? "ok" : s === "ECHEC" ? "alert" : "warn");

export function Notifications() {
  const { ui } = useParams();   // intervalles de sondage pilotés depuis la page Paramètres
  const { data, loading, error, refreshing, refetch } = usePolling(async () => {
    const [items, stats] = await Promise.all([getNotifications(), getNotifStats().catch(() => null)]);
    return { items, stats };
  }, ui.pollListeMs);
  const [onlyAdmin, setOnlyAdmin] = useState(false);

  const items = [...(data?.items ?? [])].sort((a, b) => b.id - a.id);
  const rows = onlyAdmin ? items.filter((n) => ADMIN_TYPES.includes(n.type)) : items;
  const { pageRows, page, setPage, totalPages, total, sortKey, sortDir, toggleSort } =
    useTableView<NotificationItem>(rows, { pageSize: 25, initialSort: "id", initialDir: "desc" });

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Notifications & alertes</h1><p className="text-ink-soft text-sm">Chargement…</p></div>
        <SkeletonStats /><Panel className="p-4"><SkeletonTable /></Panel>
      </div>
    );
  }
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Notifications & alertes</h1>
          <p className="text-ink-soft text-sm">Historique des notifications parents et alertes admin.</p>
        </div>
        <RefreshCw size={14} className={`shrink-0 ${refreshing ? "animate-spin text-route" : "text-ink-soft"}`} />
      </div>

      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat label="Total" value={data!.stats?.total ?? items.length} tone="route" />
        <Stat label="Envoyées" value={data!.stats?.envoyes ?? 0} tone="ok" />
        <Stat label="Échecs" value={data!.stats?.echecs ?? 0} tone="alert" />
        <Stat label="Alertes admin" value={items.filter((n) => ADMIN_TYPES.includes(n.type)).length} tone="warn" />
      </div>

      <Panel className="p-4">
        <div className="flex items-center justify-between mb-3 gap-2">
          <SectionTitle sub={`${total} entrées`}>Journal</SectionTitle>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
              <input type="checkbox" checked={onlyAdmin} onChange={(e) => setOnlyAdmin(e.target.checked)} className="accent-[var(--warn)] size-4" />
              Alertes admin
            </label>
            <button onClick={() => exportCsv("notifications", rows as unknown as Record<string, unknown>[])}
              className="inline-flex items-center gap-1.5 text-sm text-ink-soft hover:text-ink transition-colors">
              <Download size={15} /> CSV
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line">
                <SortTh label="Type" active={sortKey === "type"} dir={sortDir} onClick={() => toggleSort("type")} />
                <th className="py-2 pr-3">Titre</th>
                <th className="py-2 pr-3">Cible</th>
                <SortTh label="Statut" active={sortKey === "statutEnvoi"} dir={sortDir} onClick={() => toggleSort("statutEnvoi")} />
                <SortTh label="Date" active={sortKey === "id"} dir={sortDir} onClick={() => toggleSort("id")} />
              </tr>
            </thead>
            <tbody>
              {pageRows.map((n) => (
                <tr key={n.id} className="border-b border-line/60">
                  <td className="py-2 pr-3"><StatusChip tone={typeTone(n.type)}>{n.type}</StatusChip></td>
                  <td className="py-2 pr-3 max-w-[280px] truncate">{n.titre}</td>
                  <td className="py-2 pr-3 tabular text-ink-soft">{n.sourceType === "ADMIN" ? "admin" : n.parentId ? `parent ${n.parentId}` : "—"}</td>
                  <td className="py-2 pr-3"><StatusChip tone={envoiTone(n.statutEnvoi)}>{n.statutEnvoi}</StatusChip></td>
                  <td className="py-2 tabular text-ink-soft">{new Date(n.dateEnvoi).toLocaleString("fr-FR")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {total === 0 && <EmptyState message={onlyAdmin ? "Aucune alerte admin." : "Aucune notification."} />}
          <Pager page={page} totalPages={totalPages} total={total} onPage={setPage} />
        </div>
      </Panel>
    </div>
  );
}
