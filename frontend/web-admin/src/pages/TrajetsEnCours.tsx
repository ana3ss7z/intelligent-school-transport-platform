import { RefreshCw, Route as RouteIcon } from "lucide-react";
import { usePolling } from "../hooks/usePolling";
import { getTrajetsActifs } from "../api/endpoints";
import { Panel, Stat, StatusChip, SectionTitle } from "../components/ui";
import { SkeletonStats, SkeletonTable } from "../components/Skeleton";
import { ErrorState, EmptyState } from "../components/AsyncState";
import { useParams } from "../params/ParamsContext";

const ecoule = (iso: string) => {
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)}h${String(min % 60).padStart(2, "0")}`;
};

export function TrajetsEnCours() {
  const { ui } = useParams();   // intervalles de sondage pilotés depuis la page Paramètres
  const { data, loading, error, refreshing, refetch } = usePolling(getTrajetsActifs, ui.pollListeMs);

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Trajets en cours</h1><p className="text-ink-soft text-sm">Chargement…</p></div>
        <SkeletonStats n={3} /><Panel className="p-4"><SkeletonTable /></Panel>
      </div>
    );
  }
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;

  const trajets = data ?? [];
  const matin = trajets.filter((t) => t.sens === "MATIN").length;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Trajets en cours</h1>
          <p className="text-ink-soft text-sm">Chauffeurs actuellement en tournée (temps réel).</p>
        </div>
        <RefreshCw size={14} className={`shrink-0 ${refreshing ? "animate-spin text-route" : "text-ink-soft"}`} />
      </div>

      <div className="grid gap-3 grid-cols-3">
        <Stat label="En cours" value={trajets.length} tone="ok" />
        <Stat label="Matin" value={matin} tone="route" />
        <Stat label="Soir" value={trajets.length - matin} tone="line2" />
      </div>

      <Panel className="p-4">
        <SectionTitle sub={`${trajets.length} trajets actifs`}>Tournées en direct</SectionTitle>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line">
                <th className="py-2 pr-3">Trajet</th><th className="py-2 pr-3">Bus</th><th className="py-2 pr-3">Chauffeur</th>
                <th className="py-2 pr-3">Sens</th><th className="py-2 pr-3">Départ</th><th className="py-2">Durée</th>
              </tr>
            </thead>
            <tbody>
              {trajets.map((t) => (
                <tr key={t.id} className="border-b border-line/60">
                  <td className="py-2 pr-3 tabular text-ink-soft">#{t.id}</td>
                  <td className="py-2 pr-3 tabular">{t.matricule}</td>
                  <td className="py-2 pr-3 tabular text-ink-soft">#{t.chauffeurId}</td>
                  <td className="py-2 pr-3"><StatusChip tone={t.sens === "MATIN" ? "route" : "line2"}>{t.sens}</StatusChip></td>
                  <td className="py-2 pr-3 tabular text-ink-soft">{new Date(t.heureDebut).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</td>
                  <td className="py-2 tabular">{ecoule(t.heureDebut)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {trajets.length === 0 && <EmptyState message="Aucun trajet en cours." icon={<RouteIcon size={22} />} />}
        </div>
      </Panel>
    </div>
  );
}
