/** Export CSV côté client (téléchargement). Échappe guillemets/points-virgules/retours ligne. */
function cell(v: unknown): string {
  if (v == null) return "";
  const s = String(v);
  return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function exportCsv(filename: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const sep = ";"; // Excel FR
  const lines = [
    cols.join(sep),
    ...rows.map((r) => cols.map((c) => cell(r[c])).join(sep)),
  ];
  const blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
