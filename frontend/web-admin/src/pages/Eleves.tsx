import { useMemo, useState } from "react";
import { Search, X, Plus, Pencil, Trash2 } from "lucide-react";
import { useAsync } from "../hooks/useAsync";
import { getEleves, assignEleveBus, createEleve, updateEleve, deleteEleve } from "../api/endpoints";
import type { Eleve, EleveInput } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useTheme } from "../hooks/useTheme";
import { useToast } from "../components/Toast";
import { Modal } from "../components/Modal";
import { MapPicker } from "../components/MapPicker";
import { Panel, StatusChip, Stat, Button } from "../components/ui";
import { SkeletonStats, SkeletonTable } from "../components/Skeleton";
import { ErrorState, EmptyState } from "../components/AsyncState";
import { lineColor } from "../lib/colors";

type Presence = "all" | "present" | "absent";
const EMPTY: EleveInput = { nom: "", prenom: "", latitude: 33.893, longitude: -5.5455 };

export function Eleves() {
  const { role } = useAuth();
  const { theme } = useTheme();
  const isAdmin = role === "ADMIN";
  const toast = useToast();
  const { data, loading, error, refetch } = useAsync(getEleves, []);

  const affecterBus = async (eleveId: number, busId: number) => {
    try { await assignEleveBus(eleveId, busId); toast.success(`Élève ${eleveId} → bus ${busId}`); refetch(); }
    catch (e: unknown) { toast.error((e as { message?: string })?.message ?? "Échec de l'affectation"); }
  };

  // ── CRUD ──
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<EleveInput>(EMPTY);
  const [saving, setSaving] = useState(false);

  const openCreate = () => { setEditId(null); setForm(EMPTY); setShowForm(true); };
  const openEdit = (e: Eleve) => {
    setEditId(e.id);
    setForm({ nom: e.nom, prenom: e.prenom, latitude: e.latitude, longitude: e.longitude,
      parentId: e.parentId, busId: e.busId, groupeId: e.groupeId, ordrePassage: e.ordrePassage });
    setShowForm(true);
  };
  const submitForm = async () => {
    if (!form.nom.trim() || !form.prenom.trim()) { toast.warn("Nom et prénom requis"); return; }
    setSaving(true);
    try {
      if (editId != null) { await updateEleve(editId, form); toast.success(`${form.prenom} ${form.nom} modifié`); }
      else { await createEleve(form); toast.success(`${form.prenom} ${form.nom} créé`); }
      setShowForm(false); refetch();
    } catch (e: unknown) {
      toast.error((e as { message?: string })?.message ?? "Échec de l'enregistrement");
    } finally { setSaving(false); }
  };
  const removeEleve = async (e: Eleve) => {
    if (!window.confirm(`Supprimer ${e.prenom} ${e.nom} ?`)) return;
    try { await deleteEleve(e.id); toast.success(`${e.prenom} ${e.nom} supprimé`); refetch(); }
    catch (err: unknown) { toast.error((err as { message?: string })?.message ?? "Échec de la suppression"); }
  };

  const [q, setQ] = useState("");
  const [busFilter, setBusFilter] = useState<string>("");
  const [groupeFilter, setGroupeFilter] = useState<string>("");
  const [presence, setPresence] = useState<Presence>("all");

  const all = data ?? [];
  const busIds = useMemo(() => [...new Set(all.map((e) => e.busId).filter((b): b is number => b != null))].sort((a, b) => a - b), [all]);
  const groupeIds = useMemo(() => [...new Set(all.map((e) => e.groupeId).filter((g): g is number => g != null))].sort((a, b) => a - b), [all]);

  const rows = useMemo(() => {
    const s = q.trim().toLowerCase();
    return all.filter((e) => {
      if (s && !`${e.prenom} ${e.nom}`.toLowerCase().includes(s)) return false;
      if (busFilter && String(e.busId ?? "") !== busFilter) return false;
      if (groupeFilter && String(e.groupeId ?? "") !== groupeFilter) return false;
      if (presence === "present" && !e.statutPresence) return false;
      if (presence === "absent" && e.statutPresence) return false;
      return true;
    });
  }, [all, q, busFilter, groupeFilter, presence]);

  const hasFilter = q || busFilter || groupeFilter || presence !== "all";
  const reset = () => { setQ(""); setBusFilter(""); setGroupeFilter(""); setPresence("all"); };

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Élèves</h1><p className="text-ink-soft text-sm">Chargement…</p></div>
        <SkeletonStats /><Panel className="p-4"><SkeletonTable rows={8} /></Panel>
      </div>
    );
  }
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const selCls = "rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route";

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Élèves</h1>
          <p className="text-ink-soft text-sm">{all.length} élèves — affectation, groupe et présence.</p>
        </div>
        {isAdmin && <Button onClick={openCreate}><Plus size={16} /> Ajouter</Button>}
      </div>

      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat label="Total" value={all.length} tone="route" />
        <Stat label="Avec bus" value={all.filter((e) => e.busId).length} tone="ok" />
        <Stat label="Avec parent" value={all.filter((e) => e.parentId).length} tone="line2" />
        <Stat label="Présents" value={all.filter((e) => e.statutPresence).length} tone="warn" />
      </div>

      <Panel className="p-4">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher…" aria-label="Rechercher un élève"
              className="w-56 rounded-lg border border-line bg-panel pl-9 pr-3 py-2 text-sm outline-none focus:border-route" />
          </div>
          <select aria-label="Filtrer par bus" value={busFilter} onChange={(e) => setBusFilter(e.target.value)} className={selCls}>
            <option value="">Tous les bus</option>
            {busIds.map((b) => <option key={b} value={b}>Bus {b}</option>)}
          </select>
          <select aria-label="Filtrer par groupe" value={groupeFilter} onChange={(e) => setGroupeFilter(e.target.value)} className={selCls}>
            <option value="">Tous les groupes</option>
            {groupeIds.map((g) => <option key={g} value={g}>Groupe {g}</option>)}
          </select>
          <select aria-label="Filtrer par présence" value={presence} onChange={(e) => setPresence(e.target.value as Presence)} className={selCls}>
            <option value="all">Présence : toutes</option>
            <option value="present">À bord</option>
            <option value="absent">Absents</option>
          </select>
          {hasFilter && (
            <button onClick={reset} className="inline-flex items-center gap-1 text-sm text-ink-soft hover:text-ink transition-colors">
              <X size={14} /> réinitialiser
            </button>
          )}
          <span className="ml-auto text-[11px] font-mono uppercase tracking-wider text-ink-soft">{rows.length} résultats</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line">
                <th className="py-2 pr-3">Élève</th><th className="py-2 pr-3">Groupe</th>
                <th className="py-2 pr-3">Bus</th><th className="py-2 pr-3">Ordre</th><th className="py-2 pr-3">Présence</th>
                {isAdmin && <th className="py-2 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 300).map((e) => (
                <tr key={e.id} className="border-b border-line/60">
                  <td className="py-2 pr-3">{e.prenom} {e.nom}</td>
                  <td className="py-2 pr-3">
                    {e.groupeId != null
                      ? <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full" style={{ background: lineColor(e.groupeId) }} /> <span className="tabular">{e.groupeId}</span></span>
                      : <span className="text-ink-soft">—</span>}
                  </td>
                  <td className="py-2 pr-3">
                    {isAdmin ? (
                      <select value={e.busId ?? ""} aria-label={`Bus de ${e.prenom} ${e.nom}`}
                        onChange={(ev) => ev.target.value && affecterBus(e.id, Number(ev.target.value))}
                        className="rounded-md border border-line bg-panel px-1.5 py-1 text-xs tabular outline-none focus:border-route">
                        <option value="">—</option>
                        {busIds.map((b) => <option key={b} value={b}>Bus {b}</option>)}
                      </select>
                    ) : <span className="tabular">{e.busId ?? <span className="text-ink-soft">—</span>}</span>}
                  </td>
                  <td className="py-2 pr-3 tabular">{e.ordrePassage ?? <span className="text-ink-soft">—</span>}</td>
                  <td className="py-2 pr-3">
                    <StatusChip tone={e.statutPresence ? "ok" : "neutral"}>{e.statutPresence ? "à bord" : "absent"}</StatusChip>
                  </td>
                  {isAdmin && (
                    <td className="py-2 text-right whitespace-nowrap">
                      <button onClick={() => openEdit(e)} aria-label={`Éditer ${e.prenom} ${e.nom}`}
                        className="text-ink-soft hover:text-route transition-colors p-1"><Pencil size={15} /></button>
                      <button onClick={() => removeEleve(e)} aria-label={`Supprimer ${e.prenom} ${e.nom}`}
                        className="text-ink-soft hover:text-alert transition-colors p-1 ml-1"><Trash2 size={15} /></button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <EmptyState message="Aucun élève ne correspond aux filtres." />}
        </div>
      </Panel>

      <Modal open={showForm} onClose={() => setShowForm(false)} title={editId != null ? "Modifier l'élève" : "Ajouter un élève"}>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="el-prenom" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Prénom</label>
              <input id="el-prenom" value={form.prenom} onChange={(e) => setForm({ ...form, prenom: e.target.value })} autoFocus
                className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route" />
            </div>
            <div>
              <label htmlFor="el-nom" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Nom</label>
              <input id="el-nom" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })}
                className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route" />
            </div>
          </div>
          <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">
              Domicile (clic ou glisser) — <span className="tabular">{form.latitude.toFixed(5)}, {form.longitude.toFixed(5)}</span>
            </div>
            <MapPicker lat={form.latitude} lng={form.longitude}
              onChange={(latitude, longitude) => setForm({ ...form, latitude, longitude })} dark={theme === "dark"} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button onClick={() => setShowForm(false)} tone="neutral" variant="ghost">Annuler</Button>
            <Button onClick={submitForm} disabled={saving}>{saving ? "Enregistrement…" : editId != null ? "Enregistrer" : "Créer l'élève"}</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
