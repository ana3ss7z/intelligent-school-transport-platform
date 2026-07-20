import { Bell, RefreshCw } from "lucide-react";
import { usePolling } from "../hooks/usePolling";
import { getMesNotifications } from "../api/endpoints";
import { Panel, StatusChip, SectionTitle } from "../components/ui";
import { SkeletonTable } from "../components/Skeleton";
import { EmptyState, ErrorState } from "../components/AsyncState";

const quand = (iso: string) => new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const tone = (t: string) =>
  t === "INCIDENT_RESOLU" ? "ok" : t === "INCIDENT_SIGNALE" ? "alert" : t === "MESSAGE_ADMIN" ? "route" : "neutral";

export function ChauffeurNotifs() {
  const { data, loading, error, refreshing, refetch } = usePolling(getMesNotifications, 15000);

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Mes notifications</h1><p className="text-ink-soft text-sm">Chargement…</p></div>
        <Panel className="p-4"><SkeletonTable /></Panel>
      </div>
    );
  }
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;

  const notifs = data ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Mes notifications</h1>
          <p className="text-ink-soft text-sm">Messages de l'administration et alertes vous concernant.</p>
        </div>
        <RefreshCw size={14} className={`shrink-0 ${refreshing ? "animate-spin text-route" : "text-ink-soft"}`} />
      </div>

      <Panel className="p-4">
        <SectionTitle sub={`${notifs.length} notification(s)`}>Boîte de réception</SectionTitle>
        {notifs.length === 0 ? (
          <EmptyState message="Aucune notification pour le moment." icon={<Bell size={22} />} />
        ) : (
          <ul className="space-y-2">
            {notifs.map((n) => (
              <li key={n.id} className="rounded-lg border border-line p-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <StatusChip tone={tone(n.type)}>{n.type}</StatusChip>
                  <span className="font-medium">{n.titre}</span>
                  <span className="ml-auto text-[11px] font-mono text-ink-soft tabular">{quand(n.dateEnvoi)}</span>
                </div>
                <p className="text-sm text-ink-soft mt-1">{n.message}</p>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
