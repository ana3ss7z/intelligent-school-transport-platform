import { useMemo, useState } from "react";
import { Search, Shield, Bus as BusIcon, User as UserIcon } from "lucide-react";
import { useAsync } from "../hooks/useAsync";
import { getUsers } from "../api/endpoints";
import type { Role } from "../api/types";
import { Panel, Stat, StatusChip } from "../components/ui";
import { SkeletonStats, SkeletonTable } from "../components/Skeleton";
import { ErrorState, EmptyState } from "../components/AsyncState";

const roleTone = (r: string) => (r === "ADMIN" ? "alert" : r === "CHAUFFEUR" ? "route" : "line2");
const RoleIcon = ({ r }: { r: string }) => (r === "ADMIN" ? <Shield size={13} /> : r === "CHAUFFEUR" ? <BusIcon size={13} /> : <UserIcon size={13} />);

export function Users() {
  const { data, loading, error, refetch } = useAsync(() => getUsers(), []);
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState<Role | "">("");

  const all = data ?? [];
  const rows = useMemo(() => {
    const s = q.trim().toLowerCase();
    return all.filter((u) => {
      if (roleFilter && u.role !== roleFilter) return false;
      if (s && !`${u.nom} ${u.email}`.toLowerCase().includes(s)) return false;
      return true;
    });
  }, [all, q, roleFilter]);

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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Utilisateurs</h1>
        <p className="text-ink-soft text-sm">{all.length} comptes — admins, chauffeurs et parents (MS7).</p>
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
              className="w-64 rounded-lg border border-line bg-panel pl-9 pr-3 py-2 text-sm outline-none focus:border-route" />
          </div>
          <select aria-label="Filtrer par rôle" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value as Role | "")}
            className="rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route">
            <option value="">Tous les rôles</option>
            <option value="ADMIN">Admins</option>
            <option value="CHAUFFEUR">Chauffeurs</option>
            <option value="PARENT">Parents</option>
          </select>
          <span className="ml-auto text-[11px] font-mono uppercase tracking-wider text-ink-soft">{rows.length} résultats</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line">
                <th className="py-2 pr-3">#</th><th className="py-2 pr-3">Nom</th><th className="py-2 pr-3">Email</th>
                <th className="py-2 pr-3">Téléphone</th><th className="py-2">Rôle</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 500).map((u) => (
                <tr key={u.id} className="border-b border-line/60">
                  <td className="py-2 pr-3 tabular text-ink-soft">{u.id}</td>
                  <td className="py-2 pr-3">{u.nom}</td>
                  <td className="py-2 pr-3 text-ink-soft">{u.email}</td>
                  <td className="py-2 pr-3 tabular text-ink-soft">{u.telephone ?? "—"}</td>
                  <td className="py-2"><StatusChip tone={roleTone(u.role)}><RoleIcon r={u.role} /> {u.role}</StatusChip></td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <EmptyState message="Aucun utilisateur ne correspond." />}
        </div>
      </Panel>
    </div>
  );
}
