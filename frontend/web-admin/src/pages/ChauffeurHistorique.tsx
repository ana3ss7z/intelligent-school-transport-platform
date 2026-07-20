import { Route as RouteIcon } from "lucide-react";
import { useAsync } from "../hooks/useAsync";
import { getMesTrajets } from "../api/endpoints";
import { Panel, StatusChip, SectionTitle, Spinner } from "../components/ui";
import { EmptyState, ErrorState } from "../components/AsyncState";

const heure = (iso: string) => new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const duree = (debut: string, fin: string | null) => {
  if (!fin) return "—";
  const min = Math.max(0, Math.round((new Date(fin).getTime() - new Date(debut).getTime()) / 60000));
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)}h${String(min % 60).padStart(2, "0")}`;
};

export function ChauffeurHistorique() {
  const { data, loading, error, refetch } = useAsync(getMesTrajets, []);

  if (loading) return <Spinner label="Chargement de l'historique…" />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const trajets = data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Mes trajets</h1>
        <p className="text-ink-soft text-sm">Historique de vos trajets terminés.</p>
      </div>

      <Panel className="p-4">
        <SectionTitle sub={`${trajets.length} trajet(s) terminé(s)`}>Trajets passés</SectionTitle>
        {trajets.length === 0 ? (
          <EmptyState message="Aucun trajet terminé pour le moment." icon={<RouteIcon size={22} />} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line">
                  <th className="py-2 pr-3">Trajet</th><th className="py-2 pr-3">Sens</th>
                  <th className="py-2 pr-3">Début</th><th className="py-2 pr-3">Fin</th><th className="py-2">Durée</th>
                </tr>
              </thead>
              <tbody>
                {trajets.map((t) => (
                  <tr key={t.id} className="border-b border-line/60">
                    <td className="py-2 pr-3 tabular text-ink-soft">#{t.id}</td>
                    <td className="py-2 pr-3"><StatusChip tone={t.sens === "MATIN" ? "route" : "line2"}>{t.sens}</StatusChip></td>
                    <td className="py-2 pr-3 tabular text-ink-soft">{heure(t.heureDebut)}</td>
                    <td className="py-2 pr-3 tabular text-ink-soft">{t.heureFin ? heure(t.heureFin) : "—"}</td>
                    <td className="py-2 tabular">{duree(t.heureDebut, t.heureFin)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
