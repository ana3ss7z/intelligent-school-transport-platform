import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { usePolling } from "../hooks/usePolling";
import { getNotifications, getNotifStats } from "../api/endpoints";
import { Panel, Stat, StatusChip, SectionTitle } from "../components/ui";
import { SkeletonStats, SkeletonTable } from "../components/Skeleton";
import { ErrorState, EmptyState } from "../components/AsyncState";

const ADMIN_TYPES = ["ALERTE_QUALITE", "ANOMALIE_DETECTEE"];
const typeTone = (t: string) =>
  t.startsWith("INCIDENT") || t === "ANOMALIE_DETECTEE" ? "alert"
  : t === "ALERTE_QUALITE" || t === "RETARD" ? "warn"
  : t === "ENFANT_A_BORD" || t === "BUS_ARRIVE_ECOLE" ? "ok" : "route";
const envoiTone = (s: string) => (s === "ENVOYE" ? "ok" : s === "ECHEC" ? "alert" : "warn");

export function Notifications() {
  const { data, loading, error, refreshing, refetch } = usePolling(async () => {
    const [items, stats] = await Promise.all([getNotifications(), getNotifStats().catch(() => null)]);
    return { items, stats };
  }, 15000);
  const [onlyAdmin, setOnlyAdmin] = useState(false);

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Notifications & alertes</h1><p className="text-ink-soft text-sm">Chargement…</p></div>
        <SkeletonStats /><Panel className="p-4"><SkeletonTable /></Panel>
      </div>
    );
  }
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;

  const items = [...data!.items].sort((a, b) => b.id - a.id);
  const rows = onlyAdmin ? items.filter((n) => ADMIN_TYPES.includes(n.type)) : items;

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
        <div className="flex items-center justify-between mb-3">
          <SectionTitle sub={`${rows.length} entrées`}>Journal</SectionTitle>
          <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
            <input type="checkbox" checked={onlyAdmin} onChange={(e) => setOnlyAdmin(e.target.checked)} className="accent-[var(--warn)] size-4" />
            Alertes admin uniquement
          </label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line">
                <th className="py-2 pr-3">Type</th><th className="py-2 pr-3">Titre</th>
                <th className="py-2 pr-3">Cible</th><th className="py-2 pr-3">Statut</th><th className="py-2">Date</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 200).map((n) => (
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
          {rows.length === 0 && <EmptyState message={onlyAdmin ? "Aucune alerte admin." : "Aucune notification."} />}
        </div>
      </Panel>
    </div>
  );
}
