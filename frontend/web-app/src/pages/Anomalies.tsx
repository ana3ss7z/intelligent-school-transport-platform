import { useState } from "react";
import { Radar, ScanSearch } from "lucide-react";
import { useAsync } from "../hooks/useAsync";
import { getAnomalyModelInfo, getAnomalyScan } from "../api/endpoints";
import { useToast } from "../components/Toast";
import { Panel, Stat, Button, StatusChip, SectionTitle } from "../components/ui";
import { SkeletonStats } from "../components/Skeleton";
import { ErrorState, EmptyState } from "../components/AsyncState";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;

const fmt = (v: unknown) => (typeof v === "number" ? (Math.abs(v) < 1 ? v.toFixed(3) : v.toFixed(2)) : v == null ? "—" : String(v));
const pick = (o: Any, ...keys: string[]) => { for (const k of keys) if (o?.[k] != null) return o[k]; return undefined; };

export function Anomalies() {
  const toast = useToast();
  const { data: info, loading, error, refetch } = useAsync<Any>(getAnomalyModelInfo, []);
  const [scan, setScan] = useState<Any>(null);
  const [busy, setBusy] = useState(false);

  const lancerScan = async () => {
    setBusy(true);
    try { const r = await getAnomalyScan(20); setScan(r); toast.info("Scan du dataset terminé"); }
    catch (e: unknown) { toast.error((e as { message?: string })?.message ?? "Échec du scan"); }
    finally { setBusy(false); }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Analytique — anomalies</h1><p className="text-ink-soft text-sm">Chargement…</p></div>
        <SkeletonStats />
      </div>
    );
  }
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const m = (info?.metrics_test ?? info?.metrics ?? info) as Any;
  const detecteur = pick(info, "detecteur", "detector", "modele") ?? "—";
  const anomalies = (scan?.top_anomalies ?? scan?.anomalies ?? scan?.top ?? []) as Any[];
  const precision = pick(scan, "precision", "précision");
  const recall = pick(scan, "recall", "rappel");

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Analytique — anomalies</h1>
          <p className="text-ink-soft text-sm">Détecteur ML par trajet (MS11). Le live GPS est sur le tableau de bord.</p>
        </div>
        <StatusChip tone="line2"><Radar size={12} /> {String(detecteur)}</StatusChip>
      </div>

      {/* Métriques du détecteur */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat label="PR-AUC" value={fmt(pick(m, "PR_AUC", "pr_auc", "PR-AUC", "prauc"))} tone="line2" />
        <Stat label="ROC-AUC" value={fmt(pick(m, "ROC_AUC", "roc_auc", "ROC-AUC", "rocauc"))} tone="route" />
        <Stat label="F1" value={fmt(pick(m, "F1", "f1"))} tone="ok" />
        <Stat label="Contamination" value={fmt(pick(info, "contamination", "contam"))} tone="warn" />
      </div>

      <Panel className="p-4">
        <div className="flex items-center justify-between mb-3 gap-2">
          <SectionTitle sub="Top anomalies du dataset + précision/rappel vs incidents réels">Scan du dataset</SectionTitle>
          <Button onClick={lancerScan} variant="ghost" disabled={busy}>
            <ScanSearch size={16} /> {busy ? "Scan…" : "Lancer un scan"}
          </Button>
        </div>

        {!scan ? (
          <EmptyState message="Lance un scan pour voir les trajets les plus anormaux." icon={<ScanSearch size={22} />} />
        ) : (
          <>
            <div className="flex gap-2 mb-3">
              {precision != null && <StatusChip tone="ok">précision {fmt(precision)}</StatusChip>}
              {recall != null && <StatusChip tone="route">rappel {fmt(recall)}</StatusChip>}
              <StatusChip tone="neutral">{anomalies.length} trajets</StatusChip>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] font-mono uppercase tracking-wider text-ink-soft text-left border-b border-line">
                    <th className="py-2 pr-3">#</th><th className="py-2 pr-3">Score</th><th className="py-2 pr-3">Ratio</th>
                    <th className="py-2 pr-3">Type réel</th><th className="py-2">Détail</th>
                  </tr>
                </thead>
                <tbody>
                  {anomalies.slice(0, 20).map((a, i) => {
                    const real = pick(a, "incident_reel", "incident_type", "type_reel", "label");
                    return (
                      <tr key={i} className="border-b border-line/60">
                        <td className="py-2 pr-3 tabular text-ink-soft">{i + 1}</td>
                        <td className="py-2 pr-3 tabular">{fmt(pick(a, "anomaly_score", "score"))}</td>
                        <td className="py-2 pr-3 tabular">{fmt(pick(a, "ratio", "surprise"))}</td>
                        <td className="py-2 pr-3">
                          {real && real !== "normal" ? <StatusChip tone="alert">{String(real)}</StatusChip>
                            : <span className="text-ink-soft">normal</span>}
                        </td>
                        <td className="py-2 tabular text-ink-soft">
                          {pick(a, "duree_reelle_min", "duree_min") != null ? `${fmt(pick(a, "duree_reelle_min", "duree_min"))} min` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}
