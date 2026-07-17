import { useState } from "react";
import { Save } from "lucide-react";
import { useAsync } from "../hooks/useAsync";
import { getAnomalyModelInfo, getQuality } from "../api/endpoints";
import { getPrefs, setPrefs } from "../lib/prefs";
import { useToast } from "../components/Toast";
import { Panel, Button, SectionTitle, StatusChip } from "../components/ui";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;
const fmt = (v: unknown) => (typeof v === "number" ? (Math.abs(v) < 1 ? v.toFixed(3) : String(v)) : v == null ? "—" : String(v));

export function Settings() {
  const toast = useToast();
  const [prefs, setLocal] = useState(getPrefs());
  const { data: ano } = useAsync<Any>(getAnomalyModelInfo, []);
  const { data: quality } = useAsync<Any>(getQuality, []);

  const save = () => { setPrefs(prefs); toast.success("Préférences enregistrées"); };

  const seuils = ano?.seuils ?? ano;
  const plancher = quality?.plancher_silhouette ?? quality?.baseline?.silhouette;

  const inp = "w-32 rounded-lg border border-line bg-panel px-3 py-2 tabular text-sm outline-none focus:border-route";

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl">Paramètres</h1>
        <p className="text-ink-soft text-sm">Préférences de la console et seuils du backend.</p>
      </div>

      <Panel className="p-4">
        <SectionTitle sub="Valeurs par défaut du formulaire de clustering (stockées dans ce navigateur)">
          Défauts clustering
        </SectionTitle>
        <div className="flex flex-wrap items-end gap-4">
          <label className="text-sm">
            <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Capacité bus</div>
            <input type="number" min={10} max={100} value={prefs.capacity}
              onChange={(e) => setLocal({ ...prefs, capacity: +e.target.value })} className={inp} />
          </label>
          <label className="text-sm">
            <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Rayon max (m, 0=off)</div>
            <input type="number" min={0} step={100} value={prefs.rayon}
              onChange={(e) => setLocal({ ...prefs, rayon: +e.target.value })} className={inp} />
          </label>
          <Button onClick={save}><Save size={16} /> Enregistrer</Button>
        </div>
        <p className="text-xs text-ink-soft mt-3">
          Ces valeurs pré-remplissent la page Clustering. Le réglage réel est envoyé par paramètre à chaque calcul
          (le back garde ses propres défauts `.env`).
        </p>
      </Panel>

      <Panel className="p-4">
        <SectionTitle sub="Lecture seule — définis côté backend">Seuils backend</SectionTitle>
        <ul className="space-y-2.5 text-sm">
          <li className="flex items-center justify-between">
            <span>Vitesse anormale (MS11)</span>
            <StatusChip tone="alert">{fmt(seuils?.vitesse_kmh)} km/h</StatusChip>
          </li>
          <li className="flex items-center justify-between">
            <span>Arrêt prolongé (MS11)</span>
            <StatusChip tone="warn">{fmt(seuils?.arret_min)} min</StatusChip>
          </li>
          <li className="flex items-center justify-between">
            <span>Plancher silhouette (garde-fou clustering)</span>
            <StatusChip tone="line2">{fmt(plancher)}</StatusChip>
          </li>
        </ul>
      </Panel>
    </div>
  );
}
