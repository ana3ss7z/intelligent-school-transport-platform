import { useEffect, useRef, useState } from "react";
import { Sparkles, Send, Database, ChevronDown, ChevronRight } from "lucide-react";
import { adminQuery, type ChatTurn, type AdminQueryReply } from "../api/endpoints";
import { Panel } from "../components/ui";

const SUGGESTIONS = [
  "Combien d'élèves par bus ?",
  "Quel bus a eu le plus d'incidents ce mois-ci ?",
  "Combien d'élèves n'ont pas de bus ?",
  "Taux de présence par groupe",
  "Combien de trajets terminés cette semaine ?",
];

interface Turn extends ChatTurn { data?: AdminQueryReply }

function ResultTable({ colonnes, lignes }: { colonnes: string[]; lignes: unknown[][] }) {
  if (!colonnes.length || !lignes.length) return null;
  return (
    <div className="mt-2 overflow-x-auto rounded-lg border border-line">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[10px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line bg-panel-2">
            {colonnes.map((c) => <th key={c} className="py-1.5 px-2 whitespace-nowrap">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {lignes.slice(0, 50).map((row, i) => (
            <tr key={i} className="border-b border-line/50">
              {row.map((v, j) => <td key={j} className="py-1 px-2 tabular whitespace-nowrap">{v == null ? "—" : String(v)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SqlBlock({ sql }: { sql: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 text-[11px] font-mono text-ink-soft hover:text-ink">
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />} <Database size={12} /> SQL
      </button>
      {open && (
        <pre className="mt-1 rounded-lg bg-panel-2 border border-line p-2.5 text-[11px] overflow-x-auto whitespace-pre-wrap">{sql}</pre>
      )}
    </div>
  );
}

export function AdminAssistant() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [turns, busy]);

  const envoyer = async (texte?: string) => {
    const question = (texte ?? input).trim();
    if (!question || busy) return;
    const history: ChatTurn[] = turns.slice(-6).map((t) => ({ role: t.role, content: t.content }));
    setTurns((t) => [...t, { role: "user", content: question }]);
    setInput("");
    setBusy(true);
    try {
      const r = await adminQuery(question, history);
      setTurns((t) => [...t, { role: "assistant", content: r.reply || "…", data: r }]);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { error?: string } }; message?: string })
        ?.response?.data?.error ?? "L'assistant est momentanément indisponible.";
      setTurns((t) => [...t, { role: "assistant", content: msg }]);
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl flex items-center gap-2"><Sparkles size={22} className="text-route" /> Assistant</h1>
        <p className="text-ink-soft text-sm">Posez une question en langage naturel — réponse basée sur la base (lecture seule).</p>
      </div>

      <Panel className="overflow-hidden p-0">
        <div className="flex flex-col h-[72vh]">
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {turns.length === 0 && (
              <div className="h-full grid place-items-center text-center">
                <div className="max-w-lg">
                  <Database size={32} className="mx-auto text-route mb-3" />
                  <p className="text-ink-soft text-sm mb-4">Analyse décisionnelle : incidents, présence, tournées, flotte… (SQL généré affiché, exécution en lecture seule).</p>
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
            {turns.map((t, i) => {
              const mine = t.role === "user";
              return (
                <div key={i} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                  <div className={`${mine ? "max-w-[80%] text-white rounded-2xl rounded-br-sm px-3.5 py-2.5" : "max-w-[92%] bg-panel-2 rounded-2xl rounded-bl-sm px-3.5 py-2.5"} text-sm`}
                    style={mine ? { background: "var(--route)" } : undefined}>
                    <div className="whitespace-pre-wrap break-words">{t.content}</div>
                    {!mine && t.data?.sql && <SqlBlock sql={t.data.sql} />}
                    {!mine && t.data && <ResultTable colonnes={t.data.colonnes} lignes={t.data.lignes} />}
                    {!mine && t.data?.tronque && <div className="mt-1 text-[10px] text-ink-soft">Affichage limité aux premières lignes.</div>}
                  </div>
                </div>
              );
            })}
            {busy && (
              <div className="flex justify-start">
                <div className="bg-panel-2 rounded-2xl rounded-bl-sm px-3.5 py-2.5 text-sm text-ink-soft">
                  <span className="inline-flex gap-1"><span className="animate-pulse">●</span><span className="animate-pulse [animation-delay:150ms]">●</span><span className="animate-pulse [animation-delay:300ms]">●</span></span>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="p-3 border-t border-line flex items-end gap-2">
            <textarea value={input} onChange={(e) => setInput(e.target.value)} rows={1}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); envoyer(); } }}
              placeholder="Ex. Quel bus a eu le plus d'incidents cette semaine ? (Entrée pour envoyer)"
              className="flex-1 rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route resize-none max-h-32" />
            <button onClick={() => envoyer()} disabled={busy || !input.trim()}
              className="grid place-items-center rounded-lg px-4 py-2 text-white disabled:opacity-40"
              style={{ background: "var(--route)" }} aria-label="Envoyer"><Send size={16} /></button>
          </div>
        </div>
      </Panel>
      <p className="text-xs text-ink-soft">Requêtes générées exécutées en lecture seule (rôle read-only, sans accès aux données sensibles).</p>
    </div>
  );
}
