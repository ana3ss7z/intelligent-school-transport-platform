import { useEffect, useRef, useState } from "react";
import { Sparkles, Send, Bot } from "lucide-react";
import { chatLLM, type ChatTurn } from "../api/endpoints";
import { Panel } from "../components/ui";

const SUGGESTIONS = [
  "Où est le bus de mon enfant ?",
  "Dans combien de temps arrive-t-il à l'école ?",
  "Mon enfant est-il monté dans le bus ?",
  "Y a-t-il un incident sur son bus ?",
];

export function ParentAssistant() {
  const [msgs, setMsgs] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  const envoyer = async (texte?: string) => {
    const message = (texte ?? input).trim();
    if (!message || busy) return;
    const history = msgs.slice(-8); // derniers tours (le back borne aussi)
    setMsgs((m) => [...m, { role: "user", content: message }]);
    setInput("");
    setBusy(true);
    try {
      const r = await chatLLM(message, history);
      setMsgs((m) => [...m, { role: "assistant", content: r.reply || "…" }]);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { error?: string } }; message?: string })
        ?.response?.data?.error ?? "L'assistant est momentanément indisponible.";
      setMsgs((m) => [...m, { role: "assistant", content: msg }]);
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl flex items-center gap-2"><Sparkles size={22} className="text-route" /> Assistant</h1>
        <p className="text-ink-soft text-sm">Posez vos questions sur le transport de votre enfant (temps réel).</p>
      </div>

      <Panel className="overflow-hidden p-0">
        <div className="flex flex-col h-[70vh]">
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {msgs.length === 0 && (
              <div className="h-full grid place-items-center text-center">
                <div className="max-w-sm">
                  <Bot size={34} className="mx-auto text-route mb-3" />
                  <p className="text-ink-soft text-sm mb-4">Je peux vous renseigner sur la position du bus, l'heure d'arrivée, la présence de votre enfant et les incidents.</p>
                  <div className="flex flex-wrap justify-center gap-2">
                    {SUGGESTIONS.map((s) => (
                      <button key={s} onClick={() => envoyer(s)}
                        className="text-sm rounded-full border border-line px-3 py-1.5 text-ink-soft hover:text-ink hover:border-route transition-colors">
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
            {msgs.map((m, i) => {
              const mine = m.role === "user";
              return (
                <div key={i} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm whitespace-pre-wrap break-words ${mine ? "text-white rounded-br-sm" : "bg-panel-2 rounded-bl-sm"}`}
                    style={mine ? { background: "var(--route)" } : undefined}>
                    {m.content}
                  </div>
                </div>
              );
            })}
            {busy && (
              <div className="flex justify-start">
                <div className="bg-panel-2 rounded-2xl rounded-bl-sm px-3.5 py-2.5 text-sm text-ink-soft">
                  <span className="inline-flex gap-1">
                    <span className="animate-pulse">●</span><span className="animate-pulse [animation-delay:150ms]">●</span><span className="animate-pulse [animation-delay:300ms]">●</span>
                  </span>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="p-3 border-t border-line flex items-end gap-2">
            <textarea value={input} onChange={(e) => setInput(e.target.value)} rows={1}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); envoyer(); } }}
              placeholder="Écrire un message… (Entrée pour envoyer)"
              className="flex-1 rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route resize-none max-h-32" />
            <button onClick={() => envoyer()} disabled={busy || !input.trim()}
              className="grid place-items-center rounded-lg px-4 py-2 text-white disabled:opacity-40"
              style={{ background: "var(--route)" }} aria-label="Envoyer">
              <Send size={16} />
            </button>
          </div>
        </div>
      </Panel>
      <p className="text-xs text-ink-soft">L'assistant s'appuie sur les données réelles de votre enfant (position, ETA, présence, incidents).</p>
    </div>
  );
}
