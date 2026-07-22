import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  LayoutDashboard, Map, Network, Bell, GraduationCap, Bus as BusIcon,
  Siren, ShieldAlert, Users as UsersIcon, Clock, Route as RouteIcon, MessageSquare, Sparkles, Settings as SettingsIcon, Sun, Moon, LogOut, Search, Menu,
} from "lucide-react";
import type { Role } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useTheme } from "../hooks/useTheme";
import { useUnreadMessages } from "../hooks/useUnreadMessages";
import { CommandPalette } from "../components/CommandPalette";

interface NavItem { to: string; label: string; Icon: typeof Map; roles: Role[]; }

const NAV: NavItem[] = [
  { to: "/", label: "Tableau de bord", Icon: LayoutDashboard, roles: ["ADMIN"] },
  { to: "/chauffeur", label: "Ma tournée", Icon: RouteIcon, roles: ["CHAUFFEUR"] },
  { to: "/chauffeur/carte", label: "Carte", Icon: Map, roles: ["CHAUFFEUR"] },
  { to: "/chauffeur/eta", label: "ETA tournée", Icon: Clock, roles: ["CHAUFFEUR"] },
  { to: "/chauffeur/incidents", label: "Mes incidents", Icon: Siren, roles: ["CHAUFFEUR"] },
  { to: "/chauffeur/notifications", label: "Mes notifications", Icon: Bell, roles: ["CHAUFFEUR"] },
  { to: "/chauffeur/historique", label: "Mes trajets", Icon: Clock, roles: ["CHAUFFEUR"] },
  { to: "/messages", label: "Messagerie", Icon: MessageSquare, roles: ["ADMIN", "CHAUFFEUR"] },
  { to: "/parent", label: "Mon espace", Icon: LayoutDashboard, roles: ["PARENT"] },
  { to: "/parent/assistant", label: "Assistant", Icon: Sparkles, roles: ["PARENT"] },
  { to: "/parent/carte", label: "Carte de mon enfant", Icon: Map, roles: ["PARENT"] },
  { to: "/parent/messages", label: "Messagerie", Icon: MessageSquare, roles: ["PARENT"] },
  { to: "/parent/notifications", label: "Notifications", Icon: Bell, roles: ["PARENT"] },
  { to: "/carte", label: "Carte live", Icon: Map, roles: ["ADMIN"] },
  { to: "/clustering", label: "Clustering", Icon: Network, roles: ["ADMIN"] },
  { to: "/trajets", label: "Trajets en cours", Icon: RouteIcon, roles: ["ADMIN"] },
  { to: "/eta", label: "Prévisions ETA", Icon: Clock, roles: ["ADMIN"] },
  { to: "/incidents", label: "Incidents", Icon: Siren, roles: ["ADMIN"] },
  { to: "/anomalies", label: "Analytique", Icon: ShieldAlert, roles: ["ADMIN"] },
  { to: "/notifications", label: "Notifications", Icon: Bell, roles: ["ADMIN"] },
  { to: "/eleves", label: "Élèves", Icon: GraduationCap, roles: ["ADMIN"] },
  { to: "/bus", label: "Bus & tournées", Icon: BusIcon, roles: ["ADMIN"] },
  { to: "/users", label: "Utilisateurs", Icon: UsersIcon, roles: ["ADMIN"] },
  { to: "/settings", label: "Paramètres", Icon: SettingsIcon, roles: ["ADMIN"] },
];

/** Contenu du rail « ligne + stations » — partagé entre le rail desktop et le drawer mobile. */
function NavContent({ items, role, nom, unread }: { items: NavItem[]; role: Role | null; nom?: string; unread?: number }) {
  return (
    <>
      <div className="px-5 h-16 flex items-center gap-2.5 border-b border-line shrink-0">
        <span className="grid place-items-center size-8 rounded-lg" style={{ background: "var(--header)" }}>
          <BusIcon size={18} color="#fff" />
        </span>
        <div className="leading-tight">
          <div className="font-display font-semibold text-[15px] text-header">Transport Meknès</div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-ink-soft">console admin</div>
        </div>
      </div>

      <nav className="relative flex-1 py-4 pl-6 pr-3 overflow-y-auto">
        <span className="station-line absolute left-[27px] top-6 bottom-6 w-0.5 rounded bg-line" aria-hidden />
        <ul className="space-y-0.5">
          {items.map(({ to, label, Icon }) => (
            <li key={to}>
              <NavLink to={to} end={to === "/"}
                className="group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-ink-soft hover:text-ink hover:bg-panel-2 transition-colors [&.active]:text-ink [&.active]:bg-panel-2">
                {({ isActive }) => (
                  <>
                    <span className="absolute -left-[15px] grid place-items-center" aria-hidden>
                      <span className="size-2.5 rounded-full border-2 transition-colors"
                        style={{ borderColor: isActive ? "var(--route)" : "var(--line)", background: isActive ? "var(--route)" : "var(--panel)" }} />
                    </span>
                    <Icon size={17} />
                    <span>{label}</span>
                    {(to === "/messages" || to === "/parent/messages") && !!unread && (
                      <span className="ml-auto grid place-items-center min-w-5 h-5 px-1 rounded-full text-white text-[10px] tabular"
                        style={{ background: "var(--route)" }}>{unread}</span>
                    )}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="p-3 border-t border-line text-[11px] font-mono uppercase tracking-wider text-ink-soft shrink-0">
        {role} · {nom}
      </div>
    </>
  );
}

export function AppLayout() {
  const { user, role, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const nav = useNavigate();
  const location = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(0);
  const [drawer, setDrawer] = useState(false);
  const items = NAV.filter((i) => (role ? i.roles.includes(role) : false));
  const unread = useUnreadMessages(role === "ADMIN" || role === "CHAUFFEUR" || role === "PARENT");

  // Fermer le drawer au changement de route + sur Escape
  useEffect(() => { setDrawer(false); }, [location.pathname]);
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setDrawer(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawer]);

  return (
    <div className="min-h-svh grid grid-cols-[248px_1fr] max-md:grid-cols-1">
      {/* Rail desktop */}
      <aside className="bg-panel border-r border-line flex flex-col max-md:hidden">
        <NavContent items={items} role={role} nom={user?.nom} unread={unread} />
      </aside>

      {/* Drawer mobile */}
      {drawer && (
        <div className="fixed inset-0 z-[1050] md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setDrawer(false)} />
          <aside className="absolute left-0 top-0 h-full w-[264px] bg-panel border-r border-line flex flex-col toast-in">
            <NavContent items={items} role={role} nom={user?.nom} unread={unread} />
          </aside>
        </div>
      )}

      {/* Contenu */}
      <div className="flex flex-col min-w-0">
        <header className="h-16 shrink-0 bg-panel/80 backdrop-blur border-b border-line flex items-center justify-between px-5 sticky top-0 z-20">
          <button onClick={() => setDrawer(true)} aria-label="Ouvrir le menu"
            className="md:hidden grid place-items-center size-9 rounded-lg text-ink-soft hover:text-ink hover:bg-panel-2 transition-colors">
            <Menu size={20} />
          </button>
          <div className="md:hidden font-display font-semibold text-header">Transport Meknès</div>
          <div className="flex-1" />
          <div className="flex items-center gap-1.5">
            <button onClick={() => setPaletteOpen((v) => v + 1)} aria-label="Ouvrir la recherche (Ctrl+K)"
              className="hidden sm:flex items-center gap-2 rounded-lg border border-line px-2.5 py-1.5 text-sm text-ink-soft hover:text-ink hover:bg-panel-2 transition-colors">
              <Search size={15} /> Rechercher
              <kbd className="text-[10px] font-mono border border-line rounded px-1 py-0.5">⌘K</kbd>
            </button>
            <button onClick={toggle} aria-label="Basculer le thème"
              className="grid place-items-center size-9 rounded-lg text-ink-soft hover:text-ink hover:bg-panel-2 transition-colors">
              {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
            </button>
            <button onClick={() => { logout(); nav("/login"); }} aria-label="Se déconnecter"
              className="grid place-items-center size-9 rounded-lg text-ink-soft hover:text-alert hover:bg-panel-2 transition-colors">
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <main className="flex-1 p-5 max-w-[1400px] w-full mx-auto">
          <div key={location.pathname} className="page-in">
            <Outlet />
          </div>
        </main>
      </div>

      <CommandPalette navItems={items.map(({ to, label }) => ({ to, label }))} openSignal={paletteOpen} />
    </div>
  );
}
