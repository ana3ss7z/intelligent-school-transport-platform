import { useState } from "react";
import { TriangleAlert, Send, RefreshCw } from "lucide-react";
import { usePolling } from "../hooks/usePolling";
import { useMyBus } from "../hooks/useMyBus";
import { getIncidentsByBus, createIncident } from "../api/endpoints";
import type { TypeIncident } from "../api/types";
import { useToast } from "../components/Toast";
import { Modal } from "../components/Modal";
import { Panel, Stat, StatusChip, SectionTitle, Button, Spinner } from "../components/ui";
import { EmptyState } from "../components/AsyncState";

const TYPES: TypeIncident[] = ["PANNE", "ACCIDENT", "RETARD", "ROUTE_BLOQUEE", "ABSENCE_CHAUFFEUR", "AUTRE"];
const typeTone = (t: string) => (["ACCIDENT", "PANNE", "ROUTE_BLOQUEE"].includes(t) ? "alert" : ["RETARD", "ABSENCE_CHAUFFEUR"].includes(t) ? "warn" : "route");
const statutTone = (s: string) => (s === "RESOLU" ? "ok" : s === "EN_TRAITEMENT" ? "line2" : s === "CONFIRME" ? "route" : "warn");

export function ChauffeurIncidents() {
  const toast = useToast();
  const { myBus, loading: loadingBus } = useMyBus();
  const busId = myBus?.id ?? 0;
  const { data, loading, refreshing, refetch } = usePolling(
    () => (busId ? getIncidentsByBus(busId) : Promise.resolve([])), 15000, [busId],
  );

  const [show, setShow] = useState(false);
  const [type, setType] = useState<TypeIncident>("PANNE");
  const [desc, setDesc] = useState("");
  const [sending, setSending] = useState(false);
  const signaler = async () => {
    if (!myBus) return;
    setSending(true);
    try {
      await createIncident({ type, busId: myBus.id, description: desc || undefined });
      toast.success("Incident signalé — l'administration est prévenue");
      setShow(false); setDesc(""); refetch();
    } catch (e: unknown) {
      toast.error((e as { message?: string })?.message ?? "Échec du signalement");
    } finally { setSending(false); }
  };

  if (loadingBus || loading) return <Spinner label="Chargement des incidents…" />;
  if (!myBus) return <Panel className="p-6"><EmptyState message="Aucun bus ne vous est affecté." /></Panel>;

  const items = [...(data ?? [])].sort((a, b) => b.id - a.id);
  const ouverts = items.filter((i) => i.statut !== "RESOLU").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Mes incidents</h1>
          <p className="text-ink-soft text-sm">Bus <span className="tabular">{myBus.matricule}</span> — historique et signalement</p>
        </div>
        <div className="flex items-center gap-2">
          <RefreshCw size={14} className={refreshing ? "animate-spin text-route" : "text-ink-soft"} />
          <Button onClick={() => setShow(true)} tone="alert"><TriangleAlert size={16} /> Signaler</Button>
        </div>
      </div>

      <div className="grid gap-3 grid-cols-2 lg:grid-cols-3">
        <Stat label="Total" value={items.length} tone="route" />
        <Stat label="Ouverts" value={ouverts} tone="warn" />
        <Stat label="Résolus" value={items.length - ouverts} tone="ok" />
      </div>

      <Panel className="p-4">
        <SectionTitle sub={`${items.length} entrées`}>Journal du bus</SectionTitle>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line">
                <th className="py-2 pr-3">Type</th><th className="py-2 pr-3">Description</th>
                <th className="py-2 pr-3">Date</th><th className="py-2">Statut</th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id} className="border-b border-line/60">
                  <td className="py-2 pr-3"><StatusChip tone={typeTone(i.type)}>{i.type}</StatusChip></td>
                  <td className="py-2 pr-3 max-w-[320px] truncate" title={i.description ?? ""}>{i.description ?? "—"}</td>
                  <td className="py-2 pr-3 tabular text-ink-soft">{new Date(i.dateSignalement).toLocaleString("fr-FR")}</td>
                  <td className="py-2"><StatusChip tone={statutTone(i.statut)}>{i.statut}</StatusChip></td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && <EmptyState message="Aucun incident sur votre bus. 🚌" />}
        </div>
      </Panel>

      <Modal open={show} onClose={() => setShow(false)} title={`Signaler — bus ${myBus.matricule}`}>
        <div className="space-y-3">
          <div>
            <label htmlFor="ci-type" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Type</label>
            <select id="ci-type" value={type} onChange={(e) => setType(e.target.value as TypeIncident)}
              className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route">
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="ci-desc" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Description</label>
            <textarea id="ci-desc" value={desc} onChange={(e) => setDesc(e.target.value)} rows={3}
              className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route resize-none" />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button onClick={() => setShow(false)} tone="neutral" variant="ghost">Annuler</Button>
            <Button onClick={signaler} tone="alert" disabled={sending}><Send size={16} /> {sending ? "Envoi…" : "Signaler"}</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
