import { useMemo, useState } from "react";

export type SortDir = "asc" | "desc";

/** Tri + pagination pour une table. Les `rows` sont déjà filtrées en amont. */
export function useTableView<T>(rows: T[], opts?: { pageSize?: number; initialSort?: keyof T; initialDir?: SortDir }) {
  const pageSize = opts?.pageSize ?? 25;
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState<keyof T | null>(opts?.initialSort ?? null);
  const [sortDir, setSortDir] = useState<SortDir>(opts?.initialDir ?? "asc");

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    const arr = [...rows];
    arr.sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      let cmp: number;
      if (typeof av === "number" && typeof bv === "number") cmp = av - bv;
      else cmp = String(av).localeCompare(String(bv), "fr", { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [rows, sortKey, sortDir]);

  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageRows = useMemo(
    () => sorted.slice((safePage - 1) * pageSize, safePage * pageSize),
    [sorted, safePage, pageSize],
  );

  const toggleSort = (key: keyof T) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
    setPage(1);
  };

  return { pageRows, page: safePage, setPage, totalPages, total, pageSize, sortKey, sortDir, toggleSort };
}
