import { useEffect, useMemo, useRef, useState } from "react";
import { MessageSquare, Send, Search, Megaphone } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useMyBus } from "../hooks/useMyBus";
import {
  getMaConversation, getConversation, getConversationsAdmin, getUsers, sendMessage, diffuserParents,
} from "../api/endpoints";
import type { Conversation, Message, User } from "../api/types";
import { Panel, Button, Spinner, SectionTitle } from "../components/ui";
import { EmptyState } from "../components/AsyncState";
import { useToast } from "../components/Toast";

/** Diffusion chauffeur → tous les parents de son groupe. */
function DiffusionParents() {
  const toast = useToast();
  const { myBus } = useMyBus();
  const [txt, setTxt] = useState("");
  const [busy, setBusy] = useState(false);

  const envoyer = async () => {
    const t = txt.trim();
    if (!t || !myBus) return;
    setBusy(true);
    try {
      const r = await diffuserParents(myBus.id, t);
      toast.success(`Message diffusé à ${r.parents} parent(s).`);
      setTxt("");
    } catch (e: unknown) {
      toast.error((e as { message?: string })?.message ?? "Échec de la diffusion");
    } finally { setBusy(false); }
  };

  return (
    <Panel className="p-4">
      <SectionTitle sub="tous les parents de votre groupe">Diffusion aux parents</SectionTitle>
      <div className="flex items-end gap-2 mt-2">
        <textarea value={txt} onChange={(e) => setTxt(e.target.value)} rows={2}
          placeholder="Ex. Léger retard ce matin, ~10 min."
          className="flex-1 rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route resize-none" />
        <Button onClick={envoyer} disabled={busy || !txt.trim() || !myBus}><Megaphone size={16} /> {busy ? "…" : "Diffuser"}</Button>
      </div>
    </Panel>
  );
}

const heure = (iso: string) => new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

/** Fil de discussion (bulles) + saisie. `mine` = rôle de l'utilisateur courant. */
function Thread({ messages, mine, onSend, sending, titre, sousTitre }: {
  messages: Message[]; mine: string; onSend: (txt: string) => void; sending: boolean; titre: string; sousTitre?: string;
}) {
  const [txt, setTxt] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const submit = () => { const t = txt.trim(); if (!t) return; onSend(t); setTxt(""); };

  return (
    <div className="flex flex-col h-[70vh]">
      <div className="px-4 py-3 border-b border-line shrink-0">
        <div className="font-medium">{titre}</div>
        {sousTitre && <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft">{sousTitre}</div>}
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {messages.length === 0 ? (
          <EmptyState message="Aucun message. Démarrez la conversation." icon={<MessageSquare size={22} />} />
        ) : messages.map((m) => {
          const isMine = m.expediteurRole === mine;
          return (
            <div key={m.id} className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[78%] rounded-2xl px-3 py-2 text-sm ${isMine ? "text-white rounded-br-sm" : "bg-panel-2 rounded-bl-sm"}`}
                style={isMine ? { background: "var(--route)" } : undefined}>
                <div className="whitespace-pre-wrap break-words">{m.contenu}</div>
                <div className={`text-[10px] mt-1 tabular ${isMine ? "text-white/70" : "text-ink-soft"}`}>{heure(m.dateEnvoi)}</div>
              </div>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>
      <div className="p-3 border-t border-line shrink-0 flex items-end gap-2">
        <textarea value={txt} onChange={(e) => setTxt(e.target.value)} rows={1}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
          placeholder="Écrire un message… (Entrée pour envoyer)"
          className="flex-1 rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route resize-none max-h-32" />
        <Button onClick={submit} disabled={sending || !txt.trim()}><Send size={16} /> Envoyer</Button>
      </div>
    </div>
  );
}

/** Vue chauffeur : une seule conversation avec l'administration. */
function ChauffeurView() {
  const toast = useToast();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  const charger = () => getMaConversation().then((m) => setMessages(m)).catch(() => {}).finally(() => setLoading(false));
  useEffect(() => { charger(); const t = setInterval(charger, 10000); return () => clearInterval(t); }, []);

  const envoyer = async (contenu: string) => {
    setSending(true);
    try { await sendMessage({ contenu }); await charger(); }
    catch (e: unknown) { toast.error((e as { message?: string })?.message ?? "Échec de l'envoi"); }
    finally { setSending(false); }
  };

  if (loading) return <Spinner label="Chargement de la messagerie…" />;
  return (
    <div className="space-y-4">
      <Panel className="overflow-hidden p-0">
        <Thread messages={messages} mine="CHAUFFEUR" onSend={envoyer} sending={sending}
          titre="Administration" sousTitre="votre conversation" />
      </Panel>
      <DiffusionParents />
    </div>
  );
}

/** Vue admin : liste des chauffeurs + fil sélectionné. */
function AdminView() {
  const toast = useToast();
  const [chauffeurs, setChauffeurs] = useState<User[]>([]);
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const [q, setQ] = useState("");

  const chargerListe = () => Promise.all([getUsers("CHAUFFEUR"), getConversationsAdmin()])
    .then(([u, c]) => { setChauffeurs(u); setConvs(c); }).catch(() => {});
  useEffect(() => { chargerListe(); const t = setInterval(chargerListe, 15000); return () => clearInterval(t); }, []);

  const chargerFil = (id: number) => getConversation(id).then((m) => setMessages(m)).catch(() => {});
  useEffect(() => {
    if (sel == null) return;
    chargerFil(sel);
    const t = setInterval(() => chargerFil(sel), 10000);
    return () => clearInterval(t);
  }, [sel]);

  const convById = useMemo(() => new Map(convs.map((c) => [c.chauffeurId, c])), [convs]);
  const liste = useMemo(() => {
    const term = q.trim().toLowerCase();
    return chauffeurs
      .filter((c) => !term || c.nom.toLowerCase().includes(term) || c.email.toLowerCase().includes(term))
      .map((c) => ({ user: c, conv: convById.get(c.id) }))
      .sort((a, b) => {
        const da = a.conv ? new Date(a.conv.dateDernier).getTime() : 0;
        const db = b.conv ? new Date(b.conv.dateDernier).getTime() : 0;
        return db - da;
      });
  }, [chauffeurs, convById, q]);

  const envoyer = async (contenu: string) => {
    if (sel == null) return;
    setSending(true);
    try { await sendMessage({ destinataireId: sel, contenu }); await chargerFil(sel); await chargerListe(); }
    catch (e: unknown) { toast.error((e as { message?: string })?.message ?? "Échec de l'envoi"); }
    finally { setSending(false); }
  };

  const selUser = chauffeurs.find((c) => c.id === sel);

  return (
    <Panel className="overflow-hidden p-0">
      <div className="grid md:grid-cols-[280px_1fr]">
        {/* Liste des chauffeurs */}
        <div className="border-r border-line flex flex-col h-[70vh]">
          <div className="p-3 border-b border-line shrink-0">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-soft" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher un chauffeur…"
                className="w-full rounded-lg border border-line bg-panel pl-8 pr-3 py-1.5 text-sm outline-none focus:border-route" />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {liste.length === 0 ? <div className="p-4 text-sm text-ink-soft">Aucun chauffeur.</div> : liste.map(({ user, conv }) => (
              <button key={user.id} onClick={() => setSel(user.id)}
                className={`w-full text-left px-3 py-2.5 border-b border-line/60 hover:bg-panel-2 transition-colors ${sel === user.id ? "bg-panel-2" : ""}`}>
                <div className="flex items-center gap-2">
                  <span className="flex-1 truncate font-medium text-sm">{user.nom}</span>
                  {!!conv?.nonLus && (
                    <span className="grid place-items-center min-w-5 h-5 px-1 rounded-full text-white text-[10px] tabular" style={{ background: "var(--route)" }}>{conv.nonLus}</span>
                  )}
                </div>
                <div className="text-[11px] text-ink-soft truncate">{conv?.dernierMessage ?? "—"}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Fil sélectionné */}
        {sel == null ? (
          <div className="h-[70vh] grid place-items-center">
            <EmptyState message="Sélectionnez un chauffeur pour voir la conversation." icon={<MessageSquare size={22} />} />
          </div>
        ) : (
          <Thread messages={messages} mine="ADMIN" onSend={envoyer} sending={sending}
            titre={selUser?.nom ?? `Chauffeur #${sel}`} sousTitre={selUser?.email} />
        )}
      </div>
    </Panel>
  );
}

export function Messagerie() {
  const { role } = useAuth();
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl">Messagerie</h1>
        <p className="text-ink-soft text-sm">
          {role === "ADMIN" ? "Conversations avec les chauffeurs." : "Votre conversation avec l'administration."}
        </p>
      </div>
      {role === "ADMIN" ? <AdminView /> : <ChauffeurView />}
    </div>
  );
}
