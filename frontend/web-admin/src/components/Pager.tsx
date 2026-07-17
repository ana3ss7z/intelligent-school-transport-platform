import { ChevronLeft, ChevronRight } from "lucide-react";

/** Pagination compacte : ‹ page X / Y › + total. */
export function Pager({ page, totalPages, total, onPage }: {
  page: number; totalPages: number; total: number; onPage: (p: number) => void;
}) {
  if (total === 0) return null;
  const btn = "grid place-items-center size-8 rounded-lg border border-line text-ink-soft hover:text-ink hover:bg-panel-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed";
  return (
    <div className="flex items-center justify-between gap-3 mt-3 pt-3 border-t border-line">
      <span className="text-[11px] font-mono uppercase tracking-wider text-ink-soft">{total} entrées</span>
      <div className="flex items-center gap-2">
        <button onClick={() => onPage(page - 1)} disabled={page <= 1} aria-label="Page précédente" className={btn}>
          <ChevronLeft size={16} />
        </button>
        <span className="text-sm tabular text-ink-soft">page {page} / {totalPages}</span>
        <button onClick={() => onPage(page + 1)} disabled={page >= totalPages} aria-label="Page suivante" className={btn}>
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

/** En-tête de colonne triable. */
export function SortTh({ label, active, dir, onClick, className = "" }: {
  label: string; active: boolean; dir: "asc" | "desc"; onClick: () => void; className?: string;
}) {
  return (
    <th className={`py-2 pr-3 ${className}`}>
      <button onClick={onClick} className="inline-flex items-center gap-1 hover:text-ink transition-colors">
        {label}
        <span className={`text-[9px] ${active ? "text-route" : "text-ink-soft/40"}`}>{active ? (dir === "asc" ? "▲" : "▼") : "↕"}</span>
      </button>
    </th>
  );
}
