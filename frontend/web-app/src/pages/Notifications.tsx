import { useState } from "react";
import { RefreshCw, Download } from "lucide-react";
import { usePolling } from "../hooks/usePolling";
import { getNotifications, getNotifStats } from "../api/endpoints";
import type { NotificationItem } from "../api/types";
import { Panel, Stat, StatusChip, SectionTitle } from "../components/ui";
import { Pager, SortTh } from "../components/Pager";
import { SkeletonStats, SkeletonTable } from "../components/Skeleton";
import { ErrorState, EmptyState } from "../components/AsyncState";
import { useToast } from "../components/Toast";
import { exportCsv } from "../lib/csv";
import { useParams } from "../params/ParamsContext";

const PAGE_SIZE = 25;
/** Plafond appliqué par MS4 à une page (`TAILLE_PAGE_MAX`) — borne aussi l'export. */
const EXPORT_MAX = 500;

const typeTone = (t: string) =>
  t.startsWith("INCIDENT") || t === "ANOMALIE_DETECTEE" ? "alert"
  : t === "ALERTE_QUALITE" || t === "RETARD" ? "warn"
  : t === "ENFANT_A_BORD" || t === "BUS_ARRIVE_ECOLE" ? "ok" : "route";
const envoiTone = (s: string) => (s === "ENVOYE" ? "ok" : s === "ECHEC" ? "alert" : "warn");

type SortKey = "id" | "type" | "statutEnvoi";

/**
 * Journal des notifications.
 *
 * <p>Tri, filtre et pagination sont résolus <b>par MS4</b>. Auparavant la page téléchargeait la
 * table entière à chaque sondage pour n'en afficher que 25 lignes ; le journal dépassait
 * 10 000 entrées et grossissait de plus de mille lignes par minute pendant une simulation.
 * Conséquence directe : les totaux affichés viennent de {@code /stats} et non d'un comptage
 * local, puisque la page ne voit plus qu'une tranche.
 */
export function Notifications() {
  const { ui } = useParams();   // intervalles de sondage pilotés depuis la page Paramètres
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState<SortKey>("id");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [onlyAdmin, setOnlyAdmin] = useState(false);
  const [exporting, setExporting] = useState(false);

  const query = { page: page - 1, size: PAGE_SIZE, tri: sortKey, sens: sortDir, adminSeulement: onlyAdmin };

  const { data, loading, error, refreshing, refetch } = usePolling(
    async () => {
      const [journal, stats] = await Promise.all([
        getNotifications(query),
        getNotifStats().catch(() => null),
      ]);
      return { journal, stats };
    },
    ui.pollListeMs,
    [page, sortKey, sortDir, onlyAdmin],
  );

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
    setPage(1);   // le tri change la tranche : repartir du début, sinon la page affichée n'a plus de sens
  };

  const setFiltre = (v: boolean) => { setOnlyAdmin(v); setPage(1); };

  // L'export demande une grande page en une fois, au clic seulement — jamais à chaque sondage.
  const onExport = async () => {
    setExporting(true);
    try {
      const p = await getNotifications({ ...query, page: 0, size: EXPORT_MAX });
      exportCsv("notifications", p.content as unknown as Record<string, unknown>[]);
      if (p.total > p.content.length) {
        toast.info(`Export limité aux ${p.content.length} entrées les plus récentes sur ${p.total}.`);
      }
    } catch {
      toast.error("Export impossible.");
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Notifications & alertes</h1><p className="text-ink-soft text-sm">Chargement…</p></div>
        <SkeletonStats /><Panel className="p-4"><SkeletonTable /></Panel>
      </div>
    );
  }
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;

  const { journal, stats } = data!;

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
        <Stat label="Total" value={stats?.total ?? journal.total} tone="route" />
        <Stat label="Envoyées" value={stats?.envoyes ?? 0} tone="ok" />
        <Stat label="Échecs" value={stats?.echecs ?? 0} tone="alert" />
        <Stat label="Alertes admin" value={stats?.alertesAdmin ?? 0} tone="warn" />
      </div>

      <Panel className="p-4">
        <div className="flex items-center justify-between mb-3 gap-2">
          <SectionTitle sub={`${journal.total} entrées`}>Journal</SectionTitle>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
              <input type="checkbox" checked={onlyAdmin} onChange={(e) => setFiltre(e.target.checked)} className="accent-[var(--warn)] size-4" />
              Alertes admin
            </label>
            <button onClick={onExport} disabled={exporting}
              className="inline-flex items-center gap-1.5 text-sm text-ink-soft hover:text-ink transition-colors disabled:opacity-50">
              <Download size={15} /> {exporting ? "Export…" : "CSV"}
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
              {journal.content.map((n: NotificationItem) => (
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
          {journal.total === 0 && <EmptyState message={onlyAdmin ? "Aucune alerte admin." : "Aucune notification."} />}
          <Pager page={page} totalPages={journal.totalPages} total={journal.total} onPage={setPage} />
        </div>
      </Panel>
    </div>
  );
}
