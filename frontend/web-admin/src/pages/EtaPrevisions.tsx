import { useMemo, useState } from "react";
import { Clock, Play, MapPin, School } from "lucide-react";
import { useAsync } from "../hooks/useAsync";
import { getEleves, getTournee, predictEta } from "../api/endpoints";
import type { Eleve } from "../api/types";
import { useToast } from "../components/Toast";
import { Panel, Button, StatusChip, SectionTitle, Spinner } from "../components/ui";
import { EmptyState } from "../components/AsyncState";
import { lineColor } from "../lib/colors";

const ECOLE = { lat: 33.893, lng: -5.5455 };

interface Etape { label: string; ecole: boolean; cumul: number; arrivee: string }

const clock = (depHeure: number, min: number) => {
  const t = depHeure + min / 60;
  const h = Math.floor(t) % 24, m = Math.round((t - Math.floor(t)) * 60);
  return `${String(h).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};
const parseHeure = (hhmm: string) => { const [h, m] = hhmm.split(":").map(Number); return h + (m || 0) / 60; };

export function EtaPrevisions() {
  const toast = useToast();
  const { data: eleves } = useAsync(getEleves, []);
  const [groupe, setGroupe] = useState("");
  const [sens, setSens] = useState<"matin" | "soir">("matin");
  const [heure, setHeure] = useState("07:30");
  const [busy, setBusy] = useState(false);
  const [etapes, setEtapes] = useState<Etape[] | null>(null);
  const [total, setTotal] = useState<number | null>(null);

  const byId = useMemo(() => new Map((eleves ?? []).map((e) => [e.id, e])), [eleves]);
  const groupes = useMemo(
    () => [...new Set((eleves ?? []).map((e) => e.groupeId).filter((g): g is number => g != null))].sort((a, b) => a - b),
    [eleves],
  );

  const onSens = (s: "matin" | "soir") => { setSens(s); setHeure(s === "matin" ? "07:30" : "17:30"); };

  const calculer = async () => {
    if (!groupe) return;
    const g = Number(groupe);
    setBusy(true); setEtapes(null);
    try {
      const res = await getTournee(g, sens);
      const stops = ((res.ordre ?? []) as number[])
        .map((id) => byId.get(id)).filter((e): e is Eleve => !!e)
        .map((e) => ({ lat: e.latitude, lng: e.longitude, label: `${e.prenom} ${e.nom}`, ecole: false }));
      if (!stops.length) { toast.warn("Aucun arrêt pour ce groupe"); return; }

      // matin : école → ramassages → école (arrivée) ; soir : école → déposes
      const points = sens === "matin"
        ? [{ ...ECOLE, label: "École (départ)", ecole: true }, ...stops, { ...ECOLE, label: "École (arrivée)", ecole: true }]
        : [{ ...ECOLE, label: "École (départ)", ecole: true }, ...stops];

      // ETA de chaque tronçon (parallèle) via MS12
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
      setEtapes(out);
      setTotal(cumul);
      toast.success(`Prévisions calculées — ${stops.length} arrêts`);
    } catch (e: unknown) {
      toast.error((e as { message?: string })?.message ?? "Échec du calcul des prévisions");
    } finally { setBusy(false); }
  };

  const col = groupe ? lineColor(Number(groupe)) : "var(--route)";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Prévisions ETA par arrêt</h1>
        <p className="text-ink-soft text-sm">
          Heure d'arrivée estimée à chaque point d'une tournée (MS12). Matin = ramassage + arrivée école ; soir = dépose chez chaque parent.
        </p>
      </div>

      <Panel className="p-4 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Groupe / bus</div>
          <select value={groupe} onChange={(e) => setGroupe(e.target.value)}
            className="rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route">
            <option value="">Choisir…</option>
            {groupes.map((g) => <option key={g} value={g}>Groupe {g}</option>)}
          </select>
        </label>
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
        <Button onClick={calculer} disabled={!groupe || busy}><Play size={16} /> {busy ? "Calcul…" : "Calculer"}</Button>
        {total != null && <StatusChip tone="line2"><Clock size={12} /> tournée ~{Math.round(total)} min</StatusChip>}
      </Panel>

      {busy && <Spinner label="Prédiction des arrivées (OSRM + modèle)…" />}

      {!busy && etapes && (
        <Panel className="p-4">
          <SectionTitle sub={`Départ ${heure} · ${sens} · groupe ${groupe}`}>Arrivées estimées</SectionTitle>
          <ol className="space-y-0.5">
            {etapes.map((s, i) => (
              <li key={i} className="flex items-center gap-3 py-1.5">
                <span className="grid place-items-center size-6 shrink-0 rounded-full text-[11px] font-mono font-bold"
                  style={s.ecole
                    ? { background: "var(--surface-deep)", color: "#fff" }
                    : { background: col, color: "#fff" }}>
                  {s.ecole ? <School size={13} /> : i + 1}
                </span>
                <MapPin size={13} className="text-ink-soft shrink-0" />
                <span className="flex-1 truncate text-sm">{s.label}</span>
                <span className="tabular text-sm font-semibold" style={{ color: col }}>{s.arrivee}</span>
                <span className="tabular text-xs text-ink-soft w-16 text-right">~{Math.round(s.cumul)} min</span>
              </li>
            ))}
          </ol>
          <p className="text-xs text-ink-soft mt-3">
            {sens === "matin"
              ? "Chaque ligne = heure de ramassage de l'élève ; la dernière = arrivée à l'école."
              : "Chaque ligne = heure de dépose de l'élève chez lui (ce que voit le parent)."}
          </p>
        </Panel>
      )}

      {!busy && !etapes && (
        <Panel className="p-4"><EmptyState message="Choisis un groupe et un sens, puis calcule les prévisions." icon={<Clock size={22} />} /></Panel>
      )}
    </div>
  );
}
