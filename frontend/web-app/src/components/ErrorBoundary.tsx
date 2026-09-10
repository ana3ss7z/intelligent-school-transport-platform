import { Component, type ReactNode } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";

interface Props { children: ReactNode }
interface State { error: Error | null }

/** Empêche qu'une erreur de rendu ne blanchisse toute l'application. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: unknown) {
    console.error("[ErrorBoundary]", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-svh grid place-items-center p-6 bg-paper">
          <div className="max-w-md w-full bg-panel border border-line rounded-xl p-6 text-center">
            <span className="grid place-items-center size-12 rounded-full mx-auto mb-4"
              style={{ background: "color-mix(in oklab, var(--alert) 14%, transparent)" }}>
              <AlertTriangle style={{ color: "var(--alert)" }} />
            </span>
            <h1 className="text-lg mb-1">Une erreur est survenue</h1>
            <p className="text-sm text-ink-soft mb-4">
              L'interface a rencontré un problème inattendu. Recharge la page pour reprendre.
            </p>
            <code className="block text-xs text-ink-soft bg-panel-2 rounded-lg p-2 mb-4 break-words">
              {this.state.error.message}
            </code>
            <button onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium text-white"
              style={{ background: "var(--route)" }}>
              <RotateCw size={16} /> Recharger
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
