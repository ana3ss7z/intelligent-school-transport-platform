import { useState } from "react";
import { Play, TrendingUp } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { runProduction, getPareto, getDiagnostics, type ParetoResult } from "../api/endpoints";
import type { ProductionResult } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { Panel, Stat, Button, StatusChip, SectionTitle } from "../components/ui";
import { useToast } from "../components/Toast";
import { getPrefs } from "../lib/prefs";
import { lineColor } from "../lib/colors";

const tone = (n?: string) => (n === "CRITIQUE" ? "alert" : n === "DEGRADE" ? "warn" : "ok");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const dpick = (o: any, ...ks: string[]) => { for (const k of ks) if (o?.[k] != null) return o[k]; return undefined; };

export function Clustering() {
  const toast = useToast();
  const prefs = getPrefs();
  const [capacity, setCapacity] = useState(prefs.capacity);
  const [rayon, setRayon] = useState(prefs.rayon);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: diag } = useAsync<any>(getDiagnostics, []);
  const [appliquer, setAppliquer] = useState(false);
  const [res, setRes] = useState<ProductionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [pareto, setPareto] = useState<ParetoResult | null>(null);
  const [busyP, setBusyP] = useState(false);

  const runPareto = async () => {
    setBusyP(true);
    try { setPareto(await getPareto(capacity)); toast.info("Courbe de Pareto calculée"); }
    catch (e: unknown) { toast.error((e as { message?: string })?.message ?? "Échec Pareto"); }
    finally { setBusyP(false); }
  };

  const run = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await runProduction({ capacity, rayon, appliquer });
      setRes(r);
      const v = r.quality?.niveau ?? "OK";
      const msg = `${r.k} bus · silhouette ${r.silhouette?.toFixed(3) ?? "—"} · qualité ${v}`;
      if (appliquer) {
        if (v === "CRITIQUE") toast.warn(`Clustering appliqué mais qualité CRITIQUE — ${msg}`);
        else toast.success(`Clustering appliqué en base — ${msg}`);
      } else {
        toast.info(`Simulation terminée (non appliquée) — ${msg}`);
      }
    } catch (e: unknown) {
      const m = (e as { message?: string })?.message ?? "Erreur";
      setErr(m); toast.error(`Échec du clustering : ${m}`);
    } finally { setBusy(false); }
  };

  const dist = res ? Object.entries(res.distribution).sort((a, b) => a[0].localeCompare(b[0], undefined, { numeric: true })) : [];
  const maxN = res ? Math.max(...Object.values(res.distribution)) : 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Clustering capacitaire</h1>
        <p className="text-ink-soft text-sm">k-médoïdes sur distance routière OSRM — affectation élèves → bus.</p>
      </div>

      <Panel className="p-4 flex flex-wrap items-end gap-4">
        <label className="text-sm">
          <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Capacité bus</div>
          <input type="number" value={capacity} min={10} max={100} onChange={(e) => setCapacity(+e.target.value)}
            className="w-28 rounded-lg border border-line bg-panel px-3 py-1.5 tabular outline-none focus:border-route" />
        </label>
        <label className="text-sm">
          <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Rayon max (m, 0=off)</div>
          <input type="number" value={rayon} min={0} step={100} onChange={(e) => setRayon(+e.target.value)}
            className="w-32 rounded-lg border border-line bg-panel px-3 py-1.5 tabular outline-none focus:border-route" />
        </label>
        <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
          <input type="checkbox" checked={appliquer} onChange={(e) => setAppliquer(e.target.checked)} className="accent-[var(--route)] size-4" />
          Appliquer (écrit en base + liaison bus)
        </label>
        <Button onClick={run} disabled={busy}><Play size={16} /> {busy ? "Calcul…" : "Lancer le clustering"}</Button>
        <Button onClick={runPareto} variant="ghost" tone="line2" disabled={busyP}>
          <TrendingUp size={16} /> {busyP ? "Calcul…" : "Courbe de Pareto"}
        </Button>
        {err && <span className="text-alert text-sm">{err}</span>}
      </Panel>

      {diag && (
        <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
          <Stat label="Élèves" value={dpick(diag, "n_eleves", "nb_eleves", "total") ?? "—"} tone="route" />
          <Stat label="k recommandé" value={dpick(diag, "k_recommande", "k_recommended", "k") ?? "—"} tone="line2" hint="⌈N/capacité⌉" />
          <Stat label="Capacité" value={dpick(diag, "capacite_bus", "capacity", "bus_capacity") ?? "—"} tone="ok" />
          <Stat label="Distance" value={dpick(diag, "use_road_distance") ? "routière" : "euclidienne"} tone="warn" hint="OSRM si routière" />
        </div>
      )}

      {pareto && (
        <Panel className="p-4">
          <SectionTitle sub={`Silhouette vs nombre de bus — retenu : k=${pareto.k_retenu} (capacité ${pareto.capacity})`}>
            Courbe de Pareto (aide à la décision)
          </SectionTitle>
          <div style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={pareto.pareto} margin={{ top: 8, right: 16, bottom: 8, left: -8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis dataKey="k" stroke="var(--ink-soft)" fontSize={12} label={{ value: "nb de bus (k)", position: "insideBottom", offset: -4, fontSize: 11, fill: "var(--ink-soft)" }} />
                <YAxis stroke="var(--ink-soft)" fontSize={12} domain={[0, "auto"]} />
                <RTooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }} />
                <ReferenceLine x={pareto.k_retenu} stroke="var(--ok)" strokeDasharray="4 4" label={{ value: "retenu", fontSize: 11, fill: "var(--ok)" }} />
                <Line type="monotone" dataKey="silhouette" stroke="var(--line2)" strokeWidth={2.5} dot={{ r: 3 }} name="Silhouette" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-ink-soft mt-2">
            Le nombre de bus n'est pas arbitraire : il est choisi sur cet arbitrage qualité (silhouette) vs taille de flotte.
          </p>
        </Panel>
      )}

      {res && (
        <>
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            <Stat label="Bus (k)" value={res.k} tone="route" />
            <Stat label="Silhouette" value={res.silhouette != null ? res.silhouette.toFixed(3) : "—"} tone="line2" />
            <Stat label="Dispersés" value={res.n_disperses + res.n_non_affectes} tone="warn" hint="ramassage individuel" />
            <Stat label="Compacité max" value={res.metrics?.compacite_max_m ?? "—"} unit="m" tone="ok" />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <Panel className="p-4 lg:col-span-2">
              <SectionTitle sub="Nombre d'élèves par bus (couleurs de ligne)">Distribution des groupes</SectionTitle>
              <ul className="space-y-1.5">
                {dist.map(([g, n]) => {
                  const id = Number(g.replace(/\D/g, ""));
                  return (
                    <li key={g} className="flex items-center gap-3">
                      <span className="w-20 text-[11px] font-mono uppercase tracking-wider text-ink-soft">{g === "groupe_999" ? "dispersés" : g}</span>
                      <div className="flex-1 h-5 rounded bg-panel-2 overflow-hidden">
                        <div className="h-full rounded" style={{ width: `${(n / maxN) * 100}%`, background: g === "groupe_999" ? "var(--ink-soft)" : lineColor(id) }} />
                      </div>
                      <span className="tabular text-sm w-8 text-right">{n}</span>
                    </li>
                  );
                })}
              </ul>
            </Panel>

            <Panel className="p-4">
              <SectionTitle sub="Garde-fou dynamique">Verdict qualité</SectionTitle>
              <div className="flex items-center gap-2 mb-3">
                <StatusChip tone={tone(res.quality?.niveau)}>{res.quality?.niveau ?? "OK"}</StatusChip>
                {res.bus_binding && <StatusChip tone="route">{res.bus_binding.n_lies} élèves liés</StatusChip>}
              </div>
              {res.quality?.raisons?.length ? (
                <ul className="text-sm text-ink-soft list-disc pl-4 space-y-1">
                  {res.quality.raisons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              ) : <p className="text-sm text-ink-soft">Aucune régression détectée vs la référence.</p>}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
