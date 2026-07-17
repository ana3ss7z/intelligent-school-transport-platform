import { useEffect, useMemo, useRef, useState } from "react";
import { Radio, Route, MapPin, Waypoints, Clock } from "lucide-react";
import { useAsync } from "../hooks/useAsync";
import { usePolling } from "../hooks/usePolling";
import { useGpsSocket } from "../hooks/useGpsSocket";
import { useTheme } from "../hooks/useTheme";
import { useToast } from "../components/Toast";
import { getEleves, getTournee, getTournees, getLiveAnomalies, predictEta } from "../api/endpoints";

const ECOLE = { lat: 33.893, lng: -5.5455 };
import { MapLive, type RouteTrace } from "../components/MapLive";
import { Panel, Button, StatusChip, Spinner } from "../components/ui";
import { lineColor } from "../lib/colors";
import type { Eleve } from "../api/types";

interface Summary { n: number; distance_km: number; duree_min: number; gain: number; stops?: { n: number; label: string }[] }

function buildStops(ordre: number[], byId: Map<number, Eleve>) {
  return ordre
    .map((id, i) => {
      const e = byId.get(id);
      return e ? { n: i + 1, lat: e.latitude, lng: e.longitude, label: `${e.prenom} ${e.nom}` } : null;
    })
    .filter((s): s is NonNullable<typeof s> => s != null);
}

export function CarteLive() {
  const { theme } = useTheme();
  const toast = useToast();
  const { data: eleves, loading } = useAsync(getEleves, []);
  const { positions, trails, connected } = useGpsSocket(true);
  const [routes, setRoutes] = useState<RouteTrace[]>([]);
  const [info, setInfo] = useState<Summary | null>(null);
  const [groupe, setGroupe] = useState("");
  const [sens, setSens] = useState<"matin" | "soir">("matin");
  const [busy, setBusy] = useState(false);

  // Anomalies live → bus qui pulsent sur la carte
  const { data: anoData } = usePolling(() => getLiveAnomalies(30).catch(() => ({ n: 0, anomalies: [] })), 8000);
  const anomalyBusIds = useMemo(
    () => new Set((anoData?.anomalies ?? []).map((a) => a.busId)),
    [anoData],
  );

  // ETA live bus → école (MS12), recalculé toutes les 30 s (ref pour ne pas se ré-armer à chaque ping GPS)
  const [etas, setEtas] = useState<Record<number, number>>({});
  const posRef = useRef(positions);
  posRef.current = positions;
  useEffect(() => {
    let alive = true;
    const compute = async () => {
      const buses = Object.values(posRef.current);
      if (!buses.length) return;
      const res = await Promise.all(buses.map(async (b) => {
        try {
          const r = await predictEta({ bus_lat: b.latitude, bus_lng: b.longitude, dest_lat: ECOLE.lat, dest_lng: ECOLE.lng, moment: sens });
          return [b.cibleId, r.eta_minutes] as const;
        } catch { return [b.cibleId, null] as const; }
      }));
      if (alive) setEtas(Object.fromEntries(res.filter((x): x is readonly [number, number] => x[1] != null)));
    };
    compute();
    const t = setInterval(compute, 30000);
    return () => { alive = false; clearInterval(t); };
  }, [sens]);

  const byId = useMemo(() => new Map((eleves ?? []).map((e) => [e.id, e])), [eleves]);
  const groupes = useMemo(
    () => [...new Set((eleves ?? []).map((e) => e.groupeId).filter((g): g is number => g != null))].sort((a, b) => a - b),
    [eleves],
  );

  const tracer = async () => {
    if (!groupe) return;
    const g = Number(groupe);
    setBusy(true);
    try {
      const res = await getTournee(g, sens);
      const pts = (res.geometrie ?? []) as [number, number][];
      const stops = buildStops((res.ordre ?? []) as number[], byId);
      setRoutes([{ color: lineColor(g), points: pts, stops }]);
      setInfo({
        n: res.n_arrets ?? stops.length,
        distance_km: (res.distance_m ?? 0) / 1000,
        duree_min: res.duree_min ?? 0,
        gain: res["gain_vs_baseline_%"] ?? 0,
        stops: stops.map((s) => ({ n: s.n, label: s.label })),
      });
      toast.success(`Tournée du groupe ${g} tracée (${stops.length} arrêts)`);
    } catch (e: unknown) {
      toast.error((e as { message?: string })?.message ?? "Échec du calcul de la tournée");
    } finally {
      setBusy(false);
    }
  };

  const tracerToutes = async () => {
    setBusy(true);
    toast.info("Calcul de toutes les tournées en cours… (~40 s, OSRM)");
    try {
      const res = await getTournees(sens);
      const list = (res.tournees ?? []) as Array<{ groupeId: number; geometrie: [number, number][]; ordre: number[] }>;
      setRoutes(list.map((t) => ({
        color: lineColor(t.groupeId),
        points: t.geometrie ?? [],
        stops: buildStops(t.ordre ?? [], byId),
      })));
      setInfo({ n: res.n_bus, distance_km: res.distance_totale_km, duree_min: res.duree_totale_min, gain: res["gain_moyen_%"] });
      toast.success(`${res.n_bus} tournées tracées · gain moyen ${res["gain_moyen_%"]} %`);
    } catch (e: unknown) {
      toast.error((e as { message?: string })?.message ?? "Échec du calcul des tournées");
    } finally {
      setBusy(false);
    }
  };

  const effacer = () => { setRoutes([]); setInfo(null); };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Carte live</h1>
          <p className="text-ink-soft text-sm">Bus en temps réel, groupes d'élèves et tournées.</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusChip tone={connected ? "ok" : "warn"}>
            <Radio size={12} /> {connected ? "GPS connecté" : "hors ligne"}
          </StatusChip>
          <StatusChip tone="route">{Object.keys(positions).length} bus suivis</StatusChip>
          {Object.keys(etas).length > 0 && <StatusChip tone="line2"><Clock size={12} /> ETA → école</StatusChip>}
          {anomalyBusIds.size > 0 && <StatusChip tone="alert">{anomalyBusIds.size} en anomalie</StatusChip>}
        </div>
      </div>

      <Panel className="p-3 flex flex-wrap items-center gap-2">
        <label htmlFor="tracer-groupe" className="text-[11px] font-mono uppercase tracking-wider text-ink-soft mr-1">Tracer une tournée</label>
        <select id="tracer-groupe" value={groupe} onChange={(e) => setGroupe(e.target.value)}
          className="rounded-lg border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-route">
          <option value="">Groupe…</option>
          {groupes.map((g) => <option key={g} value={g}>Groupe {g}</option>)}
        </select>
        <select id="tracer-sens" aria-label="Sens de la tournée" value={sens} onChange={(e) => setSens(e.target.value as "matin" | "soir")}
          className="rounded-lg border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-route">
          <option value="matin">Matin (ramassage)</option>
          <option value="soir">Soir (dépose)</option>
        </select>
        <Button onClick={tracer} variant="ghost" disabled={!groupe || busy}>
          <Route size={16} /> {busy ? "Calcul…" : "Tracer"}
        </Button>
        <Button onClick={tracerToutes} variant="ghost" tone="line2" disabled={busy}>
          <Waypoints size={16} /> {busy ? "Calcul…" : "Toutes"}
        </Button>
        {routes.length > 0 && <Button onClick={effacer} tone="neutral" variant="ghost">Effacer</Button>}

        {info && (
          <div className="flex items-center gap-2 ml-auto">
            <StatusChip tone="route">{info.n} {info.stops ? "arrêts" : "bus"}</StatusChip>
            <StatusChip tone="neutral">{info.distance_km.toFixed(1)} km</StatusChip>
            <StatusChip tone="neutral">{info.duree_min.toFixed(0)} min</StatusChip>
            {info.gain > 0 && <StatusChip tone="ok">−{info.gain.toFixed(0)} % vs naïf</StatusChip>}
          </div>
        )}
      </Panel>

      {loading ? <Spinner /> : (
        <div className={`grid gap-4 ${info?.stops ? "lg:grid-cols-[1fr_300px]" : ""}`}>
          <MapLive eleves={eleves ?? []} buses={positions} trails={trails} routes={routes}
            anomalyBusIds={anomalyBusIds} etas={etas} dark={theme === "dark"} />

          {info?.stops && (
            <Panel className="p-4 flex flex-col min-h-0">
              <div className="flex items-center gap-2 mb-3">
                <span className="size-2.5 rounded-full" style={{ background: lineColor(Number(groupe)) }} />
                <span className="font-display text-sm">Ordre de passage — {sens}</span>
              </div>
              <ol className="space-y-1 overflow-y-auto pr-1 text-sm">
                <li className="flex items-center gap-2.5 text-ink-soft">
                  <span className="grid place-items-center size-5 shrink-0"><MapPin size={14} /></span>
                  École (départ)
                </li>
                {info.stops.map((s) => (
                  <li key={s.n} className="flex items-center gap-2.5">
                    <span className="grid place-items-center size-5 shrink-0 rounded-full text-[10px] font-mono font-bold text-white"
                      style={{ background: lineColor(Number(groupe)) }}>{s.n}</span>
                    <span className="truncate">{s.label}</span>
                  </li>
                ))}
                <li className="flex items-center gap-2.5 text-ink-soft">
                  <span className="grid place-items-center size-5 shrink-0"><MapPin size={14} /></span>
                  École (arrivée)
                </li>
              </ol>
            </Panel>
          )}
        </div>
      )}
      <p className="text-xs text-ink-soft">
        Astuce : lance <code className="font-mono">bus_simulator.py --presence --anomalies --loop</code> pour voir les bus se déplacer.
      </p>
    </div>
  );
}
