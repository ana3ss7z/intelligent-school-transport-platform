import { useState } from "react";
import { Clock, Play, GraduationCap, School, Bus as BusIcon } from "lucide-react";
import { getEtaMesEnfants, predictEta, type EtapeEnfant } from "../api/endpoints";
import { useToast } from "../components/Toast";
import { Panel, Button, StatusChip, SectionTitle, Spinner } from "../components/ui";
import { EmptyState } from "../components/AsyncState";
import { lineColor } from "../lib/colors";

interface Prevision extends EtapeEnfant {
  etaMin: number;
  arrivee: string;
}

const clock = (dep: number, min: number) => {
  const t = dep + min / 60, h = Math.floor(t) % 24, m = Math.round((t - Math.floor(t)) * 60);
  return `${String(h).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};
const parseHeure = (s: string) => { const [h, m] = s.split(":").map(Number); return h + (m || 0) / 60; };

export function ParentEta() {
  const toast = useToast();
  const [sens, setSens] = useState<"matin" | "soir">("matin");
  const [heure, setHeure] = useState("07:30");
  const [busy, setBusy] = useState(false);
  const [prevs, setPrevs] = useState<Prevision[] | null>(null);

  const onSens = (s: "matin" | "soir") => { setSens(s); setHeure(s === "matin" ? "07:30" : "17:30"); };

  const calculer = async () => {
    setBusy(true); setPrevs(null);
    try {
      // MS5 renvoie, pour CHAQUE enfant, son rang et le cumul depuis l'école le long de la
      // tournée optimisée — les autres élèves ne sont jamais exposés.
      const { enfants } = await getEtaMesEnfants(sens);
      if (!enfants.length) { toast.warn("Aucun enfant planifié sur une tournée"); return; }
      const dep = parseHeure(heure);
      const out = await Promise.all(enfants.map(async (e) => {
        // Le cumul est une durée OSRM libre : MS12 y applique les conditions du jour.
        const r = await predictEta({
          distance_routiere_m: e.cumul_distance_m,
          duree_base_s: e.cumul_duree_s,
          moment: sens,
          heure_depart: dep,
        }).catch(() => ({ eta_minutes: e.cumul_duree_s / 60 }));
        return { ...e, etaMin: r.eta_minutes, arrivee: clock(dep, r.eta_minutes) };
      }));
      setPrevs(out);
      toast.success(`Prévisions calculées — ${out.length} enfant(s)`);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string })
        ?.response?.data?.detail ?? (e as { message?: string })?.message ?? "Échec du calcul";
      toast.error(msg);
    } finally { setBusy(false); }
  };

  const matin = sens === "matin";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Prévisions — mes enfants</h1>
        <p className="text-ink-soft text-sm">
          Heure estimée à laquelle le bus {matin ? "passe prendre" : "dépose"} chacun de vos enfants,
          d'après la tournée optimisée et les conditions du jour.
        </p>
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
          <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">
            Départ de l'école
          </div>
          <input type="time" value={heure} onChange={(e) => setHeure(e.target.value)}
            className="rounded-lg border border-line bg-panel px-3 py-2 tabular text-sm outline-none focus:border-route" />
        </label>
        <Button onClick={calculer} disabled={busy}><Play size={16} /> {busy ? "Calcul…" : "Calculer"}</Button>
      </Panel>

      {busy && <Spinner label="Prédiction des arrivées…" />}

      {!busy && prevs && (
        <Panel className="p-4">
          <SectionTitle sub={`Départ ${heure} · ${sens}`}>
            {matin ? "Passage estimé chez vous" : "Dépose estimée chez vous"}
          </SectionTitle>
          <div className="grid gap-3 sm:grid-cols-2">
            {prevs.map((p) => {
              const col = lineColor(p.groupeId ?? p.eleveId);
              return (
                <div key={p.eleveId} className="rounded-lg border border-line p-3">
                  <div className="flex items-center gap-2.5">
                    <span className="grid place-items-center size-9 rounded-lg text-white shrink-0"
                      style={{ background: col }}>
                      <GraduationCap size={18} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{p.prenom} {p.nom}</div>
                      <div className="text-[11px] text-ink-soft">
                        {p.rang}ᵉ arrêt sur {p.n_arrets}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="tabular text-lg font-semibold" style={{ color: col }}>{p.arrivee}</div>
                      <div className="tabular text-[11px] text-ink-soft">~{Math.round(p.etaMin)} min</div>
                    </div>
                  </div>
                  <div className="mt-2 pt-2 border-t border-line/60 flex flex-wrap items-center gap-2 text-[11px] text-ink-soft">
                    <BusIcon size={13} />
                    <span>Bus {p.busId ?? "—"}</span>
                    <StatusChip tone="line2">
                      <School size={11} /> {(p.cumul_distance_m / 1000).toFixed(1)} km depuis l'école
                    </StatusChip>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-3 text-[11px] text-ink-soft">
            Estimation indicative : elle dépend du trafic, de la météo et des arrêts précédents.
          </p>
        </Panel>
      )}

      {!busy && !prevs && (
        <Panel className="p-4">
          <EmptyState icon={<Clock size={22} />}
            message="Choisissez le sens et l'heure de départ, puis calculez les arrivées estimées." />
        </Panel>
      )}
    </div>
  );
}
