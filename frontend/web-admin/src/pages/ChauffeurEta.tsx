import { useMemo, useState } from "react";
import { Clock, Play, MapPin, School } from "lucide-react";
import { useMyBus } from "../hooks/useMyBus";
import { getTournee, predictEta } from "../api/endpoints";
import type { Eleve } from "../api/types";
import { useToast } from "../components/Toast";
import { Panel, Button, StatusChip, SectionTitle, Spinner } from "../components/ui";
import { EmptyState } from "../components/AsyncState";
import { lineColor } from "../lib/colors";

const ECOLE = { lat: 33.893, lng: -5.5455 };
interface Etape { label: string; ecole: boolean; cumul: number; arrivee: string }

const clock = (dep: number, min: number) => {
  const t = dep + min / 60, h = Math.floor(t) % 24, m = Math.round((t - Math.floor(t)) * 60);
  return `${String(h).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};
const parseHeure = (s: string) => { const [h, m] = s.split(":").map(Number); return h + (m || 0) / 60; };

export function ChauffeurEta() {
  const toast = useToast();
  const { myBus, eleves, groupeId, loading } = useMyBus();
  const [sens, setSens] = useState<"matin" | "soir">("matin");
  const [heure, setHeure] = useState("07:30");
  const [busy, setBusy] = useState(false);
  const [etapes, setEtapes] = useState<Etape[] | null>(null);
  const [total, setTotal] = useState<number | null>(null);

  const byId = useMemo(() => new Map(eleves.map((e) => [e.id, e])), [eleves]);
  const onSens = (s: "matin" | "soir") => { setSens(s); setHeure(s === "matin" ? "07:30" : "17:30"); };

  const calculer = async () => {
    if (groupeId == null) return;
    setBusy(true); setEtapes(null);
    try {
      const res = await getTournee(groupeId, sens);
      const stops = ((res.ordre ?? []) as number[])
        .map((id) => byId.get(id)).filter((e): e is Eleve => !!e)
        .map((e) => ({ lat: e.latitude, lng: e.longitude, label: `${e.prenom} ${e.nom}`, ecole: false }));
      if (!stops.length) { toast.warn("Aucun arrêt"); return; }
      const points = sens === "matin"
        ? [{ ...ECOLE, label: "École (départ)", ecole: true }, ...stops, { ...ECOLE, label: "École (arrivée)", ecole: true }]
        : [{ ...ECOLE, label: "École (départ)", ecole: true }, ...stops];
      const legs = await Promise.all(points.slice(0, -1).map((from, i) => {
        const to = points[i + 1];
        return predictEta({ bus_lat: from.lat, bus_lng: from.lng, dest_lat: to.lat, dest_lng: to.lng, moment: sens })
          .then((r) => r.eta_minutes).catch(() => 0);
      }));
      const dep = parseHeure(heure);
      let cumul = 0;
      const out: Etape[] = points.slice(1).map((p, i) => {
        cumul += legs[i] ?? 0;
        return { label: p.label, ecole: p.ecole, cumul, arrivee: clock(dep, cumul) };
      });
      setEtapes(out); setTotal(cumul);
      toast.success(`Prévisions calculées — ${stops.length} arrêts`);
    } catch (e: unknown) {
      toast.error((e as { message?: string })?.message ?? "Échec du calcul");
    } finally { setBusy(false); }
  };

  if (loading) return <Spinner label="Chargement…" />;
  if (!myBus) return <Panel className="p-6"><EmptyState message="Aucun bus ne vous est affecté." /></Panel>;
  const col = groupeId != null ? lineColor(groupeId) : "var(--route)";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Prévisions ETA — ma tournée</h1>
        <p className="text-ink-soft text-sm">Heure d'arrivée estimée à chaque arrêt de <span className="tabular">{myBus.matricule}</span> (groupe {groupeId ?? "—"}).</p>
      </div>

      <Panel className="p-4 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Sens</div>
          <select value={sens} onChange={(e) => onSens(e.target.value as "matin" | "soir")}
            className="rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route">
            <option value="matin">Matin (ramassage)</option>
            <option value="soir">Soir (dépose)</option>
          </select>
        </label>
        <label className="text-sm">
          <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Heure de départ</div>
          <input type="time" value={heure} onChange={(e) => setHeure(e.target.value)}
            className="rounded-lg border border-line bg-panel px-3 py-2 tabular text-sm outline-none focus:border-route" />
        </label>
        <Button onClick={calculer} disabled={busy || groupeId == null}><Play size={16} /> {busy ? "Calcul…" : "Calculer"}</Button>
        {total != null && <StatusChip tone="line2"><Clock size={12} /> tournée ~{Math.round(total)} min</StatusChip>}
      </Panel>

      {busy && <Spinner label="Prédiction des arrivées…" />}

      {!busy && etapes && (
        <Panel className="p-4">
          <SectionTitle sub={`Départ ${heure} · ${sens}`}>Arrivées estimées</SectionTitle>
          <ol className="space-y-0.5">
            {etapes.map((s, i) => (
              <li key={i} className="flex items-center gap-3 py-1.5">
                <span className="grid place-items-center size-6 shrink-0 rounded-full text-[11px] font-mono font-bold text-white"
                  style={s.ecole ? { background: "var(--header)" } : { background: col }}>
                  {s.ecole ? <School size={13} /> : i + 1}
                </span>
                <MapPin size={13} className="text-ink-soft shrink-0" />
                <span className="flex-1 truncate text-sm">{s.label}</span>
                <span className="tabular text-sm font-semibold" style={{ color: col }}>{s.arrivee}</span>
                <span className="tabular text-xs text-ink-soft w-16 text-right">~{Math.round(s.cumul)} min</span>
              </li>
            ))}
          </ol>
        </Panel>
      )}

      {!busy && !etapes && (
        <Panel className="p-4"><EmptyState message="Choisis le sens puis calcule les arrivées estimées." icon={<Clock size={22} />} /></Panel>
      )}
    </div>
  );
}
