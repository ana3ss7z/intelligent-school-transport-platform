import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, CornerDownLeft } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useTheme } from "../hooks/useTheme";

export interface PaletteItem { id: string; label: string; hint?: string; run: () => void }

/** Palette de commandes (⌘K / Ctrl+K) : navigation + actions rapides. */
export function CommandPalette({ navItems, openSignal }: { navItems: { to: string; label: string }[]; openSignal?: number }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const nav = useNavigate();
  const { logout } = useAuth();
  const { toggle } = useTheme();
  const inputRef = useRef<HTMLInputElement>(null);

  const items = useMemo<PaletteItem[]>(() => {
    const go = navItems.map((n) => ({ id: `nav:${n.to}`, label: n.label, hint: "Aller à", run: () => nav(n.to) }));
    const actions: PaletteItem[] = [
      { id: "act:theme", label: "Basculer le thème clair / sombre", hint: "Action", run: toggle },
      { id: "act:logout", label: "Se déconnecter", hint: "Action", run: () => { logout(); nav("/login"); } },
    ];
    return [...go, ...actions];
  }, [navItems, nav, toggle, logout]);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? items.filter((i) => i.label.toLowerCase().includes(s)) : items;
  }, [items, q]);

  // Raccourci global ⌘K / Ctrl+K
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault(); setOpen((o) => !o);
      } else if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Ouverture depuis le bouton de la topbar (signal incrémental)
  useEffect(() => { if (openSignal && openSignal > 0) setOpen(true); }, [openSignal]);

  useEffect(() => {
    if (open) { setQ(""); setActive(0); setTimeout(() => inputRef.current?.focus(), 30); }
  }, [open]);
  useEffect(() => { setActive(0); }, [q]);

  if (!open) return null;

  const runItem = (i: PaletteItem) => { i.run(); setOpen(false); };

  return (
    <div className="fixed inset-0 z-[1100] flex items-start justify-center pt-[15vh] px-4"
      onClick={() => setOpen(false)} role="dialog" aria-modal="true" aria-label="Palette de commandes">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
      <div className="relative w-full max-w-lg bg-panel border border-line rounded-xl shadow-2xl overflow-hidden toast-in"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2.5 px-4 border-b border-line">
          <Search size={16} className="text-ink-soft shrink-0" />
          <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Rechercher une page ou une action…"
            aria-label="Commande"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, filtered.length - 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
              else if (e.key === "Enter" && filtered[active]) { e.preventDefault(); runItem(filtered[active]); }
            }}
            className="flex-1 bg-transparent py-3.5 text-sm outline-none" />
          <kbd className="text-[10px] font-mono text-ink-soft border border-line rounded px-1.5 py-0.5">ESC</kbd>
        </div>
        <ul className="max-h-80 overflow-y-auto py-1">
          {filtered.length === 0 && <li className="px-4 py-6 text-center text-sm text-ink-soft">Aucun résultat</li>}
          {filtered.map((i, idx) => (
            <li key={i.id}>
              <button onMouseEnter={() => setActive(idx)} onClick={() => runItem(i)}
                className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors ${idx === active ? "bg-panel-2" : ""}`}>
                <span className="text-[10px] font-mono uppercase tracking-wider text-ink-soft w-14 shrink-0">{i.hint}</span>
                <span className="flex-1">{i.label}</span>
                {idx === active && <CornerDownLeft size={14} className="text-ink-soft" />}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
