import { GraduationCap, Bus as BusIcon } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useMyChildren } from "../hooks/useMyChildren";
import { Panel, Stat, StatusChip, Spinner, SectionTitle } from "../components/ui";
import { EmptyState, ErrorState } from "../components/AsyncState";
import { lineColor } from "../lib/colors";

const statutTone = (s?: string) => (s === "ACTIF" ? "ok" : s === "EN_PANNE" ? "alert" : "neutral");

export function ParentHome() {
  const { user } = useAuth();
  const { enfants, busById, loading, error, refetch } = useMyChildren();

  if (loading) return <Spinner label="Chargement de vos enfants…" />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const aBord = enfants.filter((e) => e.statutPresence).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Mon espace</h1>
        <p className="text-ink-soft text-sm">Bonjour {user?.nom} — suivi de vos enfants.</p>
      </div>

      <div className="grid gap-3 grid-cols-2 lg:grid-cols-3">
        <Stat label="Mes enfants" value={enfants.length} tone="route" />
        <Stat label="À bord" value={aBord} tone="ok" hint="actuellement dans le bus" />
        <Stat label="Bus concernés" value={new Set(enfants.map((e) => e.busId).filter(Boolean)).size} tone="line2" />
      </div>

      <Panel className="p-4">
        <SectionTitle sub={`${enfants.length} enfant(s)`}>Mes enfants</SectionTitle>
        {enfants.length === 0 ? (
          <EmptyState message="Aucun enfant rattaché à votre compte. Contactez l'administration." icon={<GraduationCap size={22} />} />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {enfants.map((e) => {
              const bus = e.busId != null ? busById.get(e.busId) : undefined;
              return (
                <div key={e.id} className="rounded-lg border border-line p-3">
                  <div className="flex items-center gap-2.5">
                    <span className="grid place-items-center size-9 rounded-lg text-white shrink-0"
                      style={{ background: lineColor(e.groupeId ?? e.id) }}>
                      <GraduationCap size={18} />
                    </span>
                    <div className="min-w-0">
                      <div className="font-medium truncate">{e.prenom} {e.nom}</div>
                      <div className="text-[11px] text-ink-soft">
                        {e.groupeId != null ? `Groupe ${e.groupeId}` : "Sans groupe"}
                      </div>
                    </div>
                    <StatusChip tone={e.statutPresence ? "ok" : "neutral"} >
                      {e.statutPresence ? "à bord" : "pas à bord"}
                    </StatusChip>
                  </div>
                  <div className="mt-2 pt-2 border-t border-line/60 flex items-center gap-2 text-sm text-ink-soft">
                    <BusIcon size={15} />
                    {bus ? (
                      <>
                        <span className="tabular">{bus.matricule}</span>
                        <StatusChip tone={statutTone(bus.statut)}>{bus.statut}</StatusChip>
                      </>
                    ) : <span>Aucun bus assigné</span>}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}
