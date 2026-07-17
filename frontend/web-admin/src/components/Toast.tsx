import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from "lucide-react";

type ToastKind = "success" | "error" | "warn" | "info";
interface Toast { id: number; kind: ToastKind; message: string; leaving?: boolean }

interface ToastApi {
  push: (kind: ToastKind, message: string) => void;
  success: (m: string) => void;
  error: (m: string) => void;
  warn: (m: string) => void;
  info: (m: string) => void;
}

const ToastCtx = createContext<ToastApi | null>(null);

const META: Record<ToastKind, { Icon: typeof Info; color: string }> = {
  success: { Icon: CheckCircle2, color: "var(--ok)" },
  error: { Icon: XCircle, color: "var(--alert)" },
  warn: { Icon: AlertTriangle, color: "var(--warn)" },
  info: { Icon: Info, color: "var(--route)" },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seq = useRef(0);

  const remove = useCallback((id: number) => {
    setToasts((t) => t.map((x) => (x.id === id ? { ...x, leaving: true } : x)));
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 200);
  }, []);

  const push = useCallback((kind: ToastKind, message: string) => {
    const id = ++seq.current;
    setToasts((t) => [...t, { id, kind, message }]);
    setTimeout(() => remove(id), 4200);
  }, [remove]);

  const api: ToastApi = {
    push,
    success: (m) => push("success", m),
    error: (m) => push("error", m),
    warn: (m) => push("warn", m),
    info: (m) => push("info", m),
  };

  return (
    <ToastCtx.Provider value={api}>
      {children}
      <div className="fixed top-4 right-4 z-[1000] flex flex-col gap-2 w-[min(360px,calc(100vw-2rem))]"
        role="region" aria-live="polite" aria-label="Notifications">
        {toasts.map(({ id, kind, message, leaving }) => {
          const { Icon, color } = META[kind];
          return (
            <div key={id}
              className={`${leaving ? "toast-out" : "toast-in"} flex items-start gap-2.5 rounded-xl border border-line bg-panel shadow-lg px-3.5 py-3`}
              role={kind === "error" ? "alert" : "status"}>
              <Icon size={18} style={{ color }} className="shrink-0 mt-0.5" />
              <span className="text-sm text-ink flex-1 min-w-0">{message}</span>
              <button onClick={() => remove(id)} aria-label="Fermer"
                className="shrink-0 text-ink-soft hover:text-ink transition-colors">
                <X size={15} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast(): ToastApi {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error("useToast doit être utilisé dans <ToastProvider>");
  return ctx;
}
