import type { ReactNode } from "react";
import { AlertTriangle, Inbox, RotateCw } from "lucide-react";
import { Panel } from "./ui";

/** Bloc d'erreur homogène avec bouton « réessayer ». */
export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <Panel className="p-6 text-center">
      <span className="grid place-items-center size-10 rounded-full mx-auto mb-3"
        style={{ background: "color-mix(in oklab, var(--alert) 14%, transparent)" }}>
        <AlertTriangle size={18} style={{ color: "var(--alert)" }} />
      </span>
      <p className="text-sm text-ink mb-1">Impossible de charger les données</p>
      {message && <p className="text-xs text-ink-soft mb-3 break-words">{message}</p>}
      {onRetry && (
        <button onClick={onRetry}
          className="inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium"
          style={{ color: "var(--route)", background: "color-mix(in oklab, var(--route) 10%, transparent)" }}>
          <RotateCw size={14} /> Réessayer
        </button>
      )}
    </Panel>
  );
}

/** État vide homogène. */
export function EmptyState({ message = "Aucune donnée", icon }: { message?: string; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-10 text-ink-soft">
      <span className="mb-2 opacity-70">{icon ?? <Inbox size={22} />}</span>
      <p className="text-sm">{message}</p>
    </div>
  );
}

interface AsyncBoundaryProps {
  loading: boolean;
  error?: string | null;
  onRetry?: () => void;
  skeleton?: ReactNode;
  isEmpty?: boolean;
  emptyMessage?: string;
  children: ReactNode;
}

/** Enveloppe loading → skeleton, erreur → ErrorState+retry, vide → EmptyState, sinon contenu. */
export function AsyncBoundary({
  loading, error, onRetry, skeleton, isEmpty, emptyMessage, children,
}: AsyncBoundaryProps) {
  if (loading) return <>{skeleton}</>;
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (isEmpty) return <EmptyState message={emptyMessage} />;
  return <>{children}</>;
}
