import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { Modal } from "./Modal";
import { Button } from "./ui";

interface ConfirmOpts { title: string; message?: string; danger?: boolean; confirmLabel?: string }
interface PromptOpts { title: string; message?: string; defaultValue?: string; placeholder?: string; confirmLabel?: string }

interface DialogApi {
  confirm: (o: ConfirmOpts) => Promise<boolean>;
  prompt: (o: PromptOpts) => Promise<string | null>;
}

const Ctx = createContext<DialogApi | null>(null);

type State =
  | { kind: "confirm"; opts: ConfirmOpts; resolve: (v: boolean) => void }
  | { kind: "prompt"; opts: PromptOpts; resolve: (v: string | null) => void }
  | null;

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>(null);
  const [text, setText] = useState("");

  const confirm = useCallback((opts: ConfirmOpts) =>
    new Promise<boolean>((resolve) => setState({ kind: "confirm", opts, resolve })), []);
  const prompt = useCallback((opts: PromptOpts) =>
    new Promise<string | null>((resolve) => { setText(opts.defaultValue ?? ""); setState({ kind: "prompt", opts, resolve }); }), []);

  const settle = (val: boolean | string | null) => {
    if (state) (state.resolve as (v: unknown) => void)(val);
    setState(null);
  };
  const cancel = () => settle(state?.kind === "prompt" ? null : false);

  return (
    <Ctx.Provider value={{ confirm, prompt }}>
      {children}
      <Modal open={!!state} onClose={cancel} title={state?.opts.title ?? ""}>
        {state && (
          <div className="space-y-4">
            {state.opts.message && <p className="text-sm text-ink-soft">{state.opts.message}</p>}
            {state.kind === "prompt" && (
              <input autoFocus value={text} onChange={(e) => setText(e.target.value)}
                placeholder={state.opts.placeholder}
                onKeyDown={(e) => { if (e.key === "Enter") settle(text); }}
                className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route" />
            )}
            <div className="flex justify-end gap-2">
              <Button onClick={cancel} tone="neutral" variant="ghost">Annuler</Button>
              {state.kind === "confirm" ? (
                <Button onClick={() => settle(true)} tone={state.opts.danger ? "alert" : "route"}>
                  {state.opts.confirmLabel ?? "Confirmer"}
                </Button>
              ) : (
                <Button onClick={() => settle(text)}>{state.opts.confirmLabel ?? "Valider"}</Button>
              )}
            </div>
          </div>
        )}
      </Modal>
    </Ctx.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useConfirm(): DialogApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useConfirm doit être utilisé dans <ConfirmProvider>");
  return ctx;
}
