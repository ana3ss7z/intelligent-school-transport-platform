import { useEffect, useState } from "react";
import { Check, Circle, Plus, Trash2, Pencil } from "lucide-react";
import { useAsync } from "../hooks/useAsync";
import { getBus, getElevesParBus, setPresence, createBus, updateBus, setBusStatut, deleteBus } from "../api/endpoints";
import type { Bus, Eleve } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Panel, StatusChip, SectionTitle, Button } from "../components/ui";
import { Modal } from "../components/Modal";
import { SkeletonTable } from "../components/Skeleton";
import { ErrorState, EmptyState } from "../components/AsyncState";
import { RouteStrip } from "../components/RouteStrip";
import { useToast } from "../components/Toast";
import { lineColor } from "../lib/colors";

const statutTone = (s: string) => (s === "ACTIF" ? "ok" : s === "EN_PANNE" ? "alert" : "neutral");
const STATUTS = ["ACTIF", "INACTIF", "EN_PANNE"];

export function BusPage() {
  const toast = useToast();
  const { role } = useAuth();
  const isAdmin = role === "ADMIN";
  const { data: bus, loading, error, refetch } = useAsync(getBus, []);
  const [sel, setSel] = useState<number | null>(null);
  const [eleves, setEleves] = useState<Eleve[]>([]);
  const [loadingEl, setLoadingEl] = useState(false);
  const [pending, setPending] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState({ matricule: "", capacite: 50, statut: "ACTIF", chauffeurId: "" });
  const [saving, setSaving] = useState(false);

  const openCreate = () => { setEditId(null); setForm({ matricule: "", capacite: 50, statut: "ACTIF", chauffeurId: "" }); setShowForm(true); };
  const openEdit = (b: Bus) => {
    setEditId(b.id);
    setForm({ matricule: b.matricule, capacite: b.capacite, statut: b.statut, chauffeurId: b.chauffeurId != null ? String(b.chauffeurId) : "" });
    setShowForm(true);
  };

  const submitBus = async () => {
    if (!form.matricule.trim()) { toast.warn("Matricule requis"); return; }
    setSaving(true);
    const payload = {
      matricule: form.matricule.trim(), capacite: form.capacite, statut: form.statut,
      chauffeurId: form.chauffeurId ? Number(form.chauffeurId) : null,
    };
    try {
      if (editId != null) { await updateBus(editId, payload); toast.success(`Bus ${form.matricule} modifié`); }
      else { await createBus(payload); toast.success(`Bus ${form.matricule} créé`); }
      setShowForm(false); refetch();
    } catch (e: unknown) {
      toast.error((e as { message?: string })?.message ?? "Échec de l'enregistrement");
    } finally { setSaving(false); }
  };

  const changeStatut = async (id: number, statut: string) => {
    try { await setBusStatut(id, statut); toast.success(`Bus ${id} → ${statut}`); refetch(); }
    catch (e: unknown) { toast.error((e as { message?: string })?.message ?? "Échec du changement de statut"); }
  };

  const removeBus = async (id: number) => {
    if (!window.confirm(`Supprimer le bus ${id} ? Cette action est irréversible.`)) return;
    try { await deleteBus(id); toast.success(`Bus ${id} supprimé`); if (sel === id) setSel(null); refetch(); }
    catch (e: unknown) { toast.error((e as { message?: string })?.message ?? "Échec de la suppression"); }
  };

  const loadEleves = (busId: number) => {
    setLoadingEl(true);
    getElevesParBus(busId).then(setEleves).catch(() => setEleves([])).finally(() => setLoadingEl(false));
  };

  useEffect(() => { if (sel != null) loadEleves(sel); }, [sel]);

  const togglePresence = async (e: Eleve) => {
    const next = !e.statutPresence;
    setPending(e.id);
    // maj optimiste
    setEleves((list) => list.map((x) => (x.id === e.id ? { ...x, statutPresence: next } : x)));
    try {
      await setPresence(e.id, next);
      toast.success(`${e.prenom} ${e.nom} — ${next ? "marqué à bord" : "marqué absent"}`);
    } catch (err: unknown) {
      // rollback
      setEleves((list) => list.map((x) => (x.id === e.id ? { ...x, statutPresence: !next } : x)));
      toast.error((err as { message?: string })?.message ?? "Échec de la mise à jour de présence");
    } finally {
      setPending(null);
    }
  };

  if (loading) return <Panel className="p-4"><SkeletonTable rows={6} /></Panel>;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const presents = eleves.filter((e) => e.statutPresence).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Bus & tournées</h1>
        <p className="text-ink-soft text-sm">Flotte, ordre de passage et pointage de présence (vue chauffeur).</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <Panel className="p-4">
          <div className="flex items-center justify-between mb-3">
            <SectionTitle sub={`${bus!.length} bus`}>Flotte</SectionTitle>
            {isAdmin && <Button onClick={openCreate} variant="ghost"><Plus size={16} /> Ajouter</Button>}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line">
                  <th className="py-2 pr-3">Bus</th><th className="py-2 pr-3">Matricule</th>
                  <th className="py-2 pr-3">Cap.</th><th className="py-2 pr-3">Statut</th>
                  <th className="py-2 pr-3">Chauffeur</th>{isAdmin && <th className="py-2 text-right">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {bus!.map((b) => (
                  <tr key={b.id} onClick={() => setSel(b.id)}
                    className={`border-b border-line/60 cursor-pointer hover:bg-panel-2 ${sel === b.id ? "bg-panel-2" : ""}`}>
                    <td className="py-2 pr-3">
                      <span className="inline-flex items-center gap-2"><span className="size-2.5 rounded-full" style={{ background: lineColor(b.id) }} /> <span className="tabular">{b.id}</span></span>
                    </td>
                    <td className="py-2 pr-3 tabular">{b.matricule}</td>
                    <td className="py-2 pr-3 tabular">{b.capacite}</td>
                    <td className="py-2 pr-3">
                      {isAdmin ? (
                        <select value={b.statut} onClick={(e) => e.stopPropagation()}
                          onChange={(e) => { e.stopPropagation(); changeStatut(b.id, e.target.value); }}
                          aria-label={`Statut du bus ${b.id}`}
                          className="rounded-md border border-line bg-panel px-1.5 py-1 text-xs outline-none focus:border-route">
                          {STATUTS.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      ) : <StatusChip tone={statutTone(b.statut)}>{b.statut}</StatusChip>}
                    </td>
                    <td className="py-2 pr-3 tabular text-ink-soft">{b.chauffeurId ?? "—"}</td>
                    {isAdmin && (
                      <td className="py-2 text-right whitespace-nowrap">
                        <button onClick={(e) => { e.stopPropagation(); openEdit(b); }} aria-label={`Éditer le bus ${b.id}`}
                          className="text-ink-soft hover:text-route transition-colors p-1"><Pencil size={15} /></button>
                        <button onClick={(e) => { e.stopPropagation(); removeBus(b.id); }} aria-label={`Supprimer le bus ${b.id}`}
                          className="text-ink-soft hover:text-alert transition-colors p-1 ml-1"><Trash2 size={15} /></button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel className="p-4">
          <SectionTitle sub={sel ? `Bus ${sel} · ${presents}/${eleves.length} à bord` : "Sélectionne un bus"}>
            Tournée & présence
          </SectionTitle>
          {sel == null ? (
            <EmptyState message="Clique sur un bus pour voir sa tournée." />
          ) : loadingEl ? <SkeletonTable rows={5} cols={2} /> : eleves.length === 0 ? (
            <EmptyState message="Aucun élève affecté à ce bus." />
          ) : (
            <>
              <RouteStrip eleves={eleves} color={lineColor(sel)} />
              <div className="mt-4 pt-3 border-t border-line">
                <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-2">Pointage (clic = à bord / absent)</div>
                <ul className="space-y-1">
                  {eleves.map((e) => (
                    <li key={e.id}>
                      <button onClick={() => togglePresence(e)} disabled={pending === e.id}
                        className="w-full flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm hover:bg-panel-2 transition-colors disabled:opacity-50 text-left">
                        <span className="grid place-items-center size-5 rounded-full shrink-0 text-white"
                          style={{ background: e.statutPresence ? "var(--ok)" : "var(--line)" }}>
                          {e.statutPresence ? <Check size={12} /> : <Circle size={10} className="text-ink-soft" />}
                        </span>
                        <span className="tabular text-ink-soft w-6">{e.ordrePassage ?? "—"}</span>
                        <span className="flex-1 truncate">{e.prenom} {e.nom}</span>
                        <StatusChip tone={e.statutPresence ? "ok" : "neutral"}>{e.statutPresence ? "à bord" : "absent"}</StatusChip>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </Panel>
      </div>

      <Modal open={showForm} onClose={() => setShowForm(false)} title={editId != null ? "Modifier le bus" : "Ajouter un bus"}>
        <div className="space-y-3">
          <div>
            <label htmlFor="bus-mat" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Matricule</label>
            <input id="bus-mat" value={form.matricule} onChange={(e) => setForm({ ...form, matricule: e.target.value })}
              placeholder="ex. 12345-A-6" autoFocus
              className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="bus-cap" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Capacité</label>
              <input id="bus-cap" type="number" min={1} max={100} value={form.capacite}
                onChange={(e) => setForm({ ...form, capacite: +e.target.value })}
                className="w-full rounded-lg border border-line bg-panel px-3 py-2 tabular text-sm outline-none focus:border-route" />
            </div>
            <div>
              <label htmlFor="bus-stat" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Statut</label>
              <select id="bus-stat" value={form.statut} onChange={(e) => setForm({ ...form, statut: e.target.value })}
                className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route">
                {STATUTS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label htmlFor="bus-chauf" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Chauffeur (ID, optionnel)</label>
            <input id="bus-chauf" type="number" min={1} value={form.chauffeurId} placeholder="—"
              onChange={(e) => setForm({ ...form, chauffeurId: e.target.value })}
              className="w-full rounded-lg border border-line bg-panel px-3 py-2 tabular text-sm outline-none focus:border-route" />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button onClick={() => setShowForm(false)} tone="neutral" variant="ghost">Annuler</Button>
            <Button onClick={submitBus} disabled={saving}>{saving ? "Enregistrement…" : editId != null ? "Enregistrer" : "Créer le bus"}</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
