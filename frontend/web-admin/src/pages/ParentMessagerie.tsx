import { MessageSquare, RefreshCw } from "lucide-react";
import { usePolling } from "../hooks/usePolling";
import { getParentInbox } from "../api/endpoints";
import { Panel, StatusChip, SectionTitle } from "../components/ui";
import { SkeletonTable } from "../components/Skeleton";
import { EmptyState, ErrorState } from "../components/AsyncState";

const quand = (iso: string) => new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

export function ParentMessagerie() {
  const { data, loading, error, refreshing, refetch } = usePolling(getParentInbox, 15000);

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Messagerie</h1><p className="text-ink-soft text-sm">Chargement…</p></div>
        <Panel className="p-4"><SkeletonTable /></Panel>
      </div>
    );
  }
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;

  const msgs = data ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Messagerie</h1>
          <p className="text-ink-soft text-sm">Messages diffusés par le chauffeur de vos enfants.</p>
        </div>
        <RefreshCw size={14} className={`shrink-0 ${refreshing ? "animate-spin text-route" : "text-ink-soft"}`} />
      </div>

      <Panel className="p-4">
        <SectionTitle sub={`${msgs.length} message(s)`}>Boîte de réception</SectionTitle>
        {msgs.length === 0 ? (
          <EmptyState message="Aucun message reçu pour le moment." icon={<MessageSquare size={22} />} />
        ) : (
          <ul className="space-y-2">
            {msgs.map((m) => (
              <li key={m.id} className="rounded-lg border border-line p-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <StatusChip tone="route">Chauffeur</StatusChip>
                  <span className="ml-auto text-[11px] font-mono text-ink-soft tabular">{quand(m.dateEnvoi)}</span>
                </div>
                <p className="text-sm mt-1 whitespace-pre-wrap break-words">{m.contenu}</p>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
