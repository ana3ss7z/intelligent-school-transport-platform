import type { Eleve } from "../api/types";

/**
 * Motif signature : la tournée d'un bus rendue comme une LIGNE de transport —
 * pastilles-stations reliées, chaque arrêt = un élève dans l'ordre `ordrePassage`.
 * Le dépôt (école) ouvre et ferme la ligne.
 */
export function RouteStrip({ eleves, color = "#2A6FDB" }: { eleves: Eleve[]; color?: string }) {
  const ordered = [...eleves].sort(
    (a, b) => (a.ordrePassage ?? 9999) - (b.ordrePassage ?? 9999),
  );
  const stops = [
    { key: "ecole-a", label: "École (départ)", sub: "dépôt", station: false },
    ...ordered.map((e) => ({
      key: `e-${e.id}`,
      label: `${e.prenom} ${e.nom}`,
      sub: e.ordrePassage != null ? `arrêt ${e.ordrePassage}` : "non planifié",
      station: true,
      present: e.statutPresence,
    })),
    { key: "ecole-b", label: "École (arrivée)", sub: "dépôt", station: false },
  ];

  return (
    <ol className="relative pl-6">
      <span
        className="station-line absolute left-[9px] top-2 bottom-2 w-0.5 rounded"
        style={{ background: color }}
        aria-hidden
      />
      {stops.map((s) => (
        <li key={s.key} className="relative py-2">
          <span
            className="absolute -left-[15px] top-3 grid place-items-center"
            aria-hidden
          >
            <span
              className="size-3 rounded-full border-2"
              style={{
                borderColor: color,
                background: s.station ? "var(--panel)" : color,
              }}
            />
          </span>
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm text-ink">{s.label}</div>
              <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft">{s.sub}</div>
            </div>
            {"present" in s && (
              <span
                className="text-[11px] font-mono uppercase tracking-wider"
                style={{ color: s.present ? "var(--ok)" : "var(--ink-soft)" }}
              >
                {s.present ? "à bord" : "—"}
              </span>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
