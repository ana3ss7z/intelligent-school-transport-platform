import { useMemo, useState } from "react";
import { Play, TrendingUp, Layers, MapPinned } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { runProduction, getPareto, getDiagnostics, getEleves, type ParetoResult } from "../api/endpoints";
import type { ProductionResult } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { useTheme } from "../hooks/useTheme";
import { Panel, Stat, Button, StatusChip, SectionTitle, Spinner } from "../components/ui";
import { ClusterMap, computeGroups } from "../components/ClusterMap";
import { useToast } from "../components/Toast";
import { getPrefs } from "../lib/prefs";
import { lineColor } from "../lib/colors";

const tone = (n?: string) => (n === "CRITIQUE" ? "alert" : n === "DEGRADE" ? "warn" : "ok");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const dpick = (o: any, ...ks: string[]) => { for (const k of ks) if (o?.[k] != null) return o[k]; return undefined; };

export function Clustering() {
  const toast = useToast();
  const { theme } = useTheme();
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

  // Dernier résultat appliqué (depuis MS2) → carte des clusters
  const { data: eleves, loading: loadingEl, refetch: refetchEleves } = useAsync(getEleves, []);
  const groups = useMemo(() => computeGroups(eleves ?? []), [eleves]);
  const [hidden, setHidden] = useState<Set<number>>(new Set());
  const [showHull, setShowHull] = useState(true);
  const [showPts, setShowPts] = useState(true);
  const toggleGroup = (g: number) =>
    setHidden((prev) => { const n = new Set(prev); n.has(g) ? n.delete(g) : n.add(g); return n; });

  // Prévisualisation : élèves ré-étiquetés selon le résultat du dernier run (appliqué ou non)
  const previewEleves = useMemo(() => {
    if (!res?.assignments || !eleves) return null;
    return eleves.map((e) => ({ ...e, groupeId: res.assignments![String(e.id)] ?? res.assignments![e.id] ?? null }));
  }, [res, eleves]);
  const previewGroups = useMemo(() => computeGroups(previewEleves ?? []), [previewEleves]);
  const [previewHidden, setPreviewHidden] = useState<Set<number>>(new Set());
  const togglePreview = (g: number) =>
    setPreviewHidden((prev) => { const n = new Set(prev); n.has(g) ? n.delete(g) : n.add(g); return n; });

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
        refetchEleves(); // rafraîchit la carte des clusters
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

      {/* Carte du dernier résultat appliqué (depuis la base) */}
      <Panel className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <SectionTitle sub={`${groups.filter((g) => !g.noise).length} groupes · ${(eleves ?? []).filter((e) => e.groupeId != null).length} élèves affectés`}>
            <span className="inline-flex items-center gap-2"><MapPinned size={18} /> Carte des groupes — dernier résultat</span>
          </SectionTitle>
          <div className="flex items-center gap-3 text-sm">
            <label className="flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" checked={showHull} onChange={(e) => setShowHull(e.target.checked)} className="accent-[var(--route)] size-4" />
              <Layers size={14} /> Enveloppes
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" checked={showPts} onChange={(e) => setShowPts(e.target.checked)} className="accent-[var(--route)] size-4" />
              Points
            </label>
          </div>
        </div>

        {loadingEl ? <Spinner label="Chargement des groupes…" /> : (
          <>
            {/* Légende cliquable = filtres par cluster */}
            <div className="flex flex-wrap gap-1.5 mb-3">
              {groups.map((gr) => {
                const off = hidden.has(gr.g);
                return (
                  <button key={gr.g} onClick={() => toggleGroup(gr.g)}
                    aria-pressed={!off}
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-mono border transition-opacity ${off ? "opacity-40" : ""}`}
                    style={{ borderColor: gr.color, color: gr.color, background: `color-mix(in oklab, ${gr.color} 12%, transparent)` }}>
                    <span className="size-2 rounded-full" style={{ background: gr.color }} />
                    {gr.noise ? "dispersés" : `G${gr.g}`} · {gr.count}
                  </button>
                );
              })}
              {groups.length === 0 && <span className="text-sm text-ink-soft">Aucun groupe en base — lance un clustering (Appliquer) ci-dessous.</span>}
            </div>
            {groups.length > 0 && (
              <ClusterMap eleves={eleves ?? []} hidden={hidden} showHull={showHull} showPts={showPts} dark={theme === "dark"} />
            )}
          </>
        )}
      </Panel>

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

      {/* Carte de prévisualisation du dernier run (appliqué ou non) */}
      {previewEleves && (
        <Panel className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <SectionTitle sub={`${res!.k} bus · silhouette ${res!.silhouette?.toFixed(3) ?? "—"} · ${res!.quality?.niveau ?? "OK"}`}>
              <span className="inline-flex items-center gap-2">
                <MapPinned size={18} /> Prévisualisation — {res!.groupes_appliques === "non demandé" ? "nouveau clustering (non appliqué)" : "résultat appliqué"}
              </span>
            </SectionTitle>
            <StatusChip tone={res!.groupes_appliques === "non demandé" ? "warn" : "ok"}>
              {res!.groupes_appliques === "non demandé" ? "simulation" : "appliqué en base"}
            </StatusChip>
          </div>
          <div className="flex flex-wrap gap-1.5 mb-3">
            {previewGroups.map((gr) => {
              const off = previewHidden.has(gr.g);
              return (
                <button key={gr.g} onClick={() => togglePreview(gr.g)} aria-pressed={!off}
                  className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-mono border transition-opacity ${off ? "opacity-40" : ""}`}
                  style={{ borderColor: gr.color, color: gr.color, background: `color-mix(in oklab, ${gr.color} 12%, transparent)` }}>
                  <span className="size-2 rounded-full" style={{ background: gr.color }} />
                  {gr.noise ? "dispersés" : `G${gr.g}`} · {gr.count}
                </button>
              );
            })}
          </div>
          <ClusterMap eleves={previewEleves} hidden={previewHidden} showHull={showHull} showPts={showPts} dark={theme === "dark"} />
          {res!.groupes_appliques === "non demandé" && (
            <p className="text-xs text-ink-soft mt-2">Aperçu non enregistré. Coche « Appliquer » puis relance pour écrire en base (met aussi à jour la carte du haut).</p>
          )}
        </Panel>
      )}

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
                {typeof res.bus_binding === "object" && res.bus_binding && <StatusChip tone="route">{res.bus_binding.n_lies} élèves liés</StatusChip>}
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
