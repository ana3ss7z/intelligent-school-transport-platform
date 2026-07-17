import { useMemo, useState } from "react";
import { Search, Shield, Bus as BusIcon, User as UserIcon, Plus, Pencil, Trash2, Download } from "lucide-react";
import { useAsync } from "../hooks/useAsync";
import { useTableView } from "../hooks/useTableView";
import { getUsers, createUser, updateUser, deleteUser } from "../api/endpoints";
import type { Role, User, UserInput } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { useConfirm } from "../components/ConfirmDialog";
import { Modal } from "../components/Modal";
import { Pager, SortTh } from "../components/Pager";
import { Panel, Stat, StatusChip, Button } from "../components/ui";
import { SkeletonStats, SkeletonTable } from "../components/Skeleton";
import { ErrorState, EmptyState } from "../components/AsyncState";
import { exportCsv } from "../lib/csv";

const roleTone = (r: string) => (r === "ADMIN" ? "alert" : r === "CHAUFFEUR" ? "route" : "line2");
const RoleIcon = ({ r }: { r: string }) => (r === "ADMIN" ? <Shield size={13} /> : r === "CHAUFFEUR" ? <BusIcon size={13} /> : <UserIcon size={13} />);
const EMPTY: UserInput = { nom: "", email: "", role: "PARENT", telephone: "", motDePasse: "" };

export function Users() {
  const { user } = useAuth();
  const toast = useToast();
  const { confirm } = useConfirm();
  const { data, loading, error, refetch } = useAsync(() => getUsers(), []);
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState<Role | "">("");

  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<UserInput>(EMPTY);
  const [saving, setSaving] = useState(false);

  const all = data ?? [];
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return all.filter((u) => {
      if (roleFilter && u.role !== roleFilter) return false;
      if (s && !`${u.nom} ${u.email}`.toLowerCase().includes(s)) return false;
      return true;
    });
  }, [all, q, roleFilter]);

  const { pageRows, page, setPage, totalPages, total, sortKey, sortDir, toggleSort } =
    useTableView<User>(filtered, { pageSize: 25, initialSort: "nom" });

  const openCreate = () => { setEditId(null); setForm(EMPTY); setShowForm(true); };
  const openEdit = (u: User) => {
    setEditId(u.id);
    setForm({ nom: u.nom, email: u.email, role: u.role, telephone: u.telephone ?? "", motDePasse: "" });
    setShowForm(true);
  };
  const submit = async () => {
    if (!form.nom.trim() || !form.email.trim()) { toast.warn("Nom et email requis"); return; }
    if (editId == null && (!form.motDePasse || form.motDePasse.length < 6)) { toast.warn("Mot de passe requis (min 6)"); return; }
    setSaving(true);
    try {
      const payload: UserInput = { ...form, motDePasse: form.motDePasse || undefined };
      if (editId != null) { await updateUser(editId, payload); toast.success(`${form.nom} modifié`); }
      else { await createUser(payload); toast.success(`${form.nom} créé`); }
      setShowForm(false); refetch();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: string }; message?: string })?.response?.data
        ?? (e as { message?: string })?.message ?? "Échec de l'enregistrement";
      toast.error(String(msg));
    } finally { setSaving(false); }
  };
  const remove = async (u: User) => {
    if (!await confirm({ title: "Supprimer l'utilisateur", message: `Supprimer ${u.nom} (${u.email}) ?`, danger: true, confirmLabel: "Supprimer" })) return;
    try { await deleteUser(u.id); toast.success(`${u.nom} supprimé`); refetch(); }
    catch (e: unknown) {
      const msg = (e as { response?: { data?: string }; message?: string })?.response?.data
        ?? (e as { message?: string })?.message ?? "Échec de la suppression";
      toast.error(String(msg));
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Utilisateurs</h1><p className="text-ink-soft text-sm">Chargement…</p></div>
        <SkeletonStats n={3} /><Panel className="p-4"><SkeletonTable /></Panel>
      </div>
    );
  }
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const count = (r: Role) => all.filter((u) => u.role === r).length;
  const inp = "rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route";

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Utilisateurs</h1>
          <p className="text-ink-soft text-sm">{all.length} comptes — admins, chauffeurs et parents (MS7).</p>
        </div>
        <Button onClick={openCreate}><Plus size={16} /> Ajouter</Button>
      </div>

      <div className="grid gap-3 grid-cols-3">
        <Stat label="Admins" value={count("ADMIN")} tone="alert" />
        <Stat label="Chauffeurs" value={count("CHAUFFEUR")} tone="route" />
        <Stat label="Parents" value={count("PARENT")} tone="line2" />
      </div>

      <Panel className="p-4">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher (nom, email)…" aria-label="Rechercher un utilisateur"
              className={`w-64 pl-9 pr-3 py-2 rounded-lg border border-line bg-panel text-sm outline-none focus:border-route`} />
          </div>
          <select aria-label="Filtrer par rôle" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value as Role | "")} className={inp}>
            <option value="">Tous les rôles</option>
            <option value="ADMIN">Admins</option>
            <option value="CHAUFFEUR">Chauffeurs</option>
            <option value="PARENT">Parents</option>
          </select>
          <button onClick={() => exportCsv("utilisateurs", filtered as unknown as Record<string, unknown>[])}
            className="inline-flex items-center gap-1.5 text-sm text-ink-soft hover:text-ink transition-colors ml-auto">
            <Download size={15} /> Exporter CSV
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line">
                <SortTh label="#" active={sortKey === "id"} dir={sortDir} onClick={() => toggleSort("id")} />
                <SortTh label="Nom" active={sortKey === "nom"} dir={sortDir} onClick={() => toggleSort("nom")} />
                <SortTh label="Email" active={sortKey === "email"} dir={sortDir} onClick={() => toggleSort("email")} />
                <th className="py-2 pr-3">Téléphone</th>
                <SortTh label="Rôle" active={sortKey === "role"} dir={sortDir} onClick={() => toggleSort("role")} />
                <th className="py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {pageRows.map((u) => (
                <tr key={u.id} className="border-b border-line/60">
                  <td className="py-2 pr-3 tabular text-ink-soft">{u.id}</td>
                  <td className="py-2 pr-3">{u.nom}</td>
                  <td className="py-2 pr-3 text-ink-soft">{u.email}</td>
                  <td className="py-2 pr-3 tabular text-ink-soft">{u.telephone ?? "—"}</td>
                  <td className="py-2 pr-3"><StatusChip tone={roleTone(u.role)}><RoleIcon r={u.role} /> {u.role}</StatusChip></td>
                  <td className="py-2 text-right whitespace-nowrap">
                    <button onClick={() => openEdit(u)} aria-label={`Éditer ${u.nom}`} className="text-ink-soft hover:text-route transition-colors p-1"><Pencil size={15} /></button>
                    {u.email !== user?.email && (
                      <button onClick={() => remove(u)} aria-label={`Supprimer ${u.nom}`} className="text-ink-soft hover:text-alert transition-colors p-1 ml-1"><Trash2 size={15} /></button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {total === 0 && <EmptyState message="Aucun utilisateur ne correspond." />}
          <Pager page={page} totalPages={totalPages} total={total} onPage={setPage} />
        </div>
      </Panel>

      <Modal open={showForm} onClose={() => setShowForm(false)} title={editId != null ? "Modifier l'utilisateur" : "Ajouter un utilisateur"}>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="u-nom" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Nom</label>
              <input id="u-nom" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} autoFocus
                className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route" />
            </div>
            <div>
              <label htmlFor="u-role" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Rôle</label>
              <select id="u-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}
                className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route">
                <option value="ADMIN">ADMIN</option><option value="CHAUFFEUR">CHAUFFEUR</option><option value="PARENT">PARENT</option>
              </select>
            </div>
          </div>
          <div>
            <label htmlFor="u-email" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Email</label>
            <input id="u-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route" />
          </div>
          <div>
            <label htmlFor="u-tel" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Téléphone</label>
            <input id="u-tel" value={form.telephone ?? ""} onChange={(e) => setForm({ ...form, telephone: e.target.value })}
              className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route" />
          </div>
          <div>
            <label htmlFor="u-pwd" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">
              Mot de passe {editId != null && <span className="normal-case tracking-normal">(laisser vide = inchangé)</span>}
            </label>
            <input id="u-pwd" type="password" value={form.motDePasse ?? ""} onChange={(e) => setForm({ ...form, motDePasse: e.target.value })}
              placeholder={editId != null ? "•••••• (inchangé)" : "min 6 caractères"} autoComplete="new-password"
              className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route" />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button onClick={() => setShowForm(false)} tone="neutral" variant="ghost">Annuler</Button>
            <Button onClick={submit} disabled={saving}>{saving ? "Enregistrement…" : editId != null ? "Enregistrer" : "Créer"}</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
