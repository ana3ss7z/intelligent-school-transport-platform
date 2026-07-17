import type { ReactNode } from "react";

type Tone = "route" | "ok" | "warn" | "alert" | "line2" | "neutral";

const toneVar: Record<Tone, string> = {
  route: "var(--route)", ok: "var(--ok)", warn: "var(--warn)",
  alert: "var(--alert)", line2: "var(--line2)", neutral: "var(--ink-soft)",
};

/** Panneau / carte — conteneur de base signalétique. */
export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-panel border border-line rounded-xl ${className}`}>{children}</div>
  );
}

/** Chip de statut — pastille couleur fonctionnelle + label mono en capitales. */
export function StatusChip({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  const c = toneVar[tone];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-mono uppercase tracking-wider"
      style={{ color: c, background: `color-mix(in oklab, ${c} 14%, transparent)` }}
    >
      <span className="inline-block size-1.5 rounded-full" style={{ background: c }} />
      {children}
    </span>
  );
}

/** Tuile KPI façon « tableau des départs » : gros chiffre mono + label signalétique. */
export function Stat({
  label, value, unit, tone = "route", hint,
}: { label: string; value: ReactNode; unit?: string; tone?: Tone; hint?: string }) {
  return (
    <Panel className="p-4 relative overflow-hidden">
      <span className="absolute left-0 top-0 h-full w-1" style={{ background: toneVar[tone] }} />
      <div className="text-[11px] font-mono uppercase tracking-[0.14em] text-ink-soft">{label}</div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="tabular text-3xl font-semibold text-ink leading-none">{value}</span>
        {unit && <span className="text-sm text-ink-soft">{unit}</span>}
      </div>
      {hint && <div className="mt-1 text-xs text-ink-soft">{hint}</div>}
    </Panel>
  );
}

export function SectionTitle({ children, sub }: { children: ReactNode; sub?: string }) {
  return (
    <div className="mb-3">
      <h2 className="text-lg">{children}</h2>
      {sub && <p className="text-sm text-ink-soft mt-0.5">{sub}</p>}
    </div>
  );
}

export function Button({
  children, onClick, tone = "route", variant = "solid", disabled, type = "button",
}: {
  children: ReactNode; onClick?: () => void; tone?: Tone;
  variant?: "solid" | "ghost"; disabled?: boolean; type?: "button" | "submit";
}) {
  const c = toneVar[tone];
  const base = "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  return (
    <button
      type={type} onClick={onClick} disabled={disabled}
      className={base}
      style={variant === "solid"
        ? { background: c, color: "#fff" }
        : { color: c, background: `color-mix(in oklab, ${c} 10%, transparent)` }}
    >
      {children}
    </button>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-ink-soft text-sm py-6 justify-center">
      <span className="size-4 rounded-full border-2 border-line border-t-route animate-spin" />
      {label ?? "Chargement…"}
    </div>
  );
}
