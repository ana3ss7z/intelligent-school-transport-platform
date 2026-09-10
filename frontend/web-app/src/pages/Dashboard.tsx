import { AlertTriangle, Activity, Bus, GraduationCap, Bell, Gauge, RefreshCw } from "lucide-react";
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip as RTooltip, ResponsiveContainer, Legend,
} from "recharts";
import { usePolling } from "../hooks/usePolling";
import {
  getEleves, getBusActifs, getNotifStats, getQuality, getLiveAnomalies,
  getEtaModelInfo, getAnomalyModelInfo, getIncidentStats,
} from "../api/endpoints";
import { Panel, Stat, SectionTitle, StatusChip } from "../components/ui";
import { SkeletonStats } from "../components/Skeleton";
import { ErrorState } from "../components/AsyncState";
import { useParams } from "../params/ParamsContext";

const niveauTone = (n?: string) =>
  n === "CRITIQUE" ? "alert" : n === "DEGRADE" ? "warn" : "ok";

const TT = { background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 };

export function Dashboard() {
  const { ui } = useParams();   // intervalles de sondage pilotés depuis la page Paramètres
  const { data, loading, error, refreshing, refetch, lastUpdated } = usePolling(async () => {
    const [eleves, bus, stats, quality, live, eta, ano, incStats] = await Promise.all([
      getEleves(), getBusActifs(), getNotifStats().catch(() => null),
      getQuality().catch(() => null), getLiveAnomalies().catch(() => null),
      getEtaModelInfo().catch(() => null), getAnomalyModelInfo().catch(() => null),
      getIncidentStats().catch(() => null),
    ]);
    return { eleves, bus, stats, quality, live, eta, ano, incStats };
  }, ui.pollListeMs);

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Tableau de bord</h1><p className="text-ink-soft text-sm">Chargement…</p></div>
        <SkeletonStats />
      </div>
    );
  }
  if (error && !data) return <ErrorState message={`${error} — lance la stack (Gateway :8080)`} onRetry={refetch} />;
  const d = data!;
  const avecBus = d.eleves.filter((e) => e.busId != null).length;
  const presents = d.eleves.filter((e) => e.statutPresence).length;
  const verdict = d.quality?.dernier_verdict?.niveau as string | undefined;
  const sil = d.quality?.baseline?.silhouette as number | undefined;
  const anomalies = d.live?.anomalies ?? [];

  // Données graphiques
  const notifData = [
    { name: "Envoyées", v: d.stats?.envoyes ?? 0, fill: "var(--ok)" },
    { name: "Échecs", v: d.stats?.echecs ?? 0, fill: "var(--alert)" },
    { name: "Attente", v: d.stats?.attente ?? 0, fill: "var(--warn)" },
  ];
  const inc = d.incStats ?? {};
  const incData = [
    { name: "Signalés", v: inc.signale ?? 0, fill: "var(--warn)" },
    { name: "Confirmés", v: inc.confirme ?? 0, fill: "var(--route)" },
    { name: "En cours", v: inc.en_traitement ?? 0, fill: "var(--line2)" },
    { name: "Résolus", v: inc.resolu ?? 0, fill: "var(--ok)" },
  ];
  const presData = [
    { name: "À bord", value: presents, fill: "var(--ok)" },
    { name: "Absents", value: Math.max(0, d.eleves.length - presents), fill: "var(--ink-soft)" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Tableau de bord</h1>
          <p className="text-ink-soft text-sm">Vue d'ensemble de la flotte, des groupes et des alertes.</p>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-ink-soft shrink-0">
          <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} style={{ color: refreshing ? "var(--route)" : undefined }} />
          {lastUpdated ? `maj ${new Date(lastUpdated).toLocaleTimeString("fr-FR")}` : "live"}
        </div>
      </div>

      {/* Departures board — KPIs */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat label="Élèves" value={d.eleves.length} tone="route" hint={`${avecBus} affectés à un bus`} />
        <Stat label="Bus actifs" value={d.bus.length} tone="ok" hint="flotte en service" />
        <Stat label="Présents" value={presents} tone="line2" hint="enfants à bord" />
        <Stat label="Notifs échec" value={d.stats?.echecs ?? "—"} tone="warn" hint={`${d.stats?.total ?? 0} au total`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Alertes live */}
        <Panel className="p-4 lg:col-span-2">
          <SectionTitle sub="Détectées en temps réel par le monitor GPS (MS11)">Anomalies live</SectionTitle>
          {anomalies.length === 0 ? (
            <div className="text-sm text-ink-soft py-6 text-center flex items-center justify-center gap-2">
              <Activity size={16} /> Aucune anomalie récente.
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {anomalies.slice(0, 6).map((a, i) => (
                <li key={i} className="flex items-center justify-between py-2.5">
                  <div className="flex items-center gap-2.5">
                    <AlertTriangle size={16} style={{ color: "var(--alert)" }} />
                    <div>
                      <div className="text-sm">Bus {a.busId} — {a.type}</div>
                      <div className="text-[11px] font-mono text-ink-soft">{new Date(a.timestamp).toLocaleTimeString("fr-FR")}</div>
                    </div>
                  </div>
                  <StatusChip tone={a.type?.includes("VITESSE") ? "alert" : "warn"}>{a.niveau ?? "alerte"}</StatusChip>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        {/* Santé système */}
        <Panel className="p-4">
          <SectionTitle sub="État des briques IA">Santé système</SectionTitle>
          <ul className="space-y-3 text-sm">
            <li className="flex items-center justify-between">
              <span className="flex items-center gap-2"><Gauge size={16} /> Qualité clustering</span>
              <StatusChip tone={niveauTone(verdict)}>{verdict ?? "OK"}</StatusChip>
            </li>
            <li className="flex items-center justify-between text-ink-soft">
              <span className="pl-6">silhouette référence</span>
              <span className="tabular">{sil != null ? sil.toFixed(3) : "—"}</span>
            </li>
            <li className="flex items-center justify-between">
              <span className="flex items-center gap-2"><Gauge size={16} /> Modèle ETA</span>
              <StatusChip tone="ok">{d.eta?.algorithme ?? "—"}</StatusChip>
            </li>
            <li className="flex items-center justify-between">
              <span className="flex items-center gap-2"><Gauge size={16} /> Détecteur anomalies</span>
              <StatusChip tone="ok">{d.ano?.detecteur ?? "—"}</StatusChip>
            </li>
          </ul>
        </Panel>
      </div>

      {/* Graphiques */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Panel className="p-4">
          <SectionTitle sub="Statut d'envoi">Notifications</SectionTitle>
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={notifData} margin={{ top: 4, right: 8, bottom: 4, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis dataKey="name" stroke="var(--ink-soft)" fontSize={11} />
                <YAxis stroke="var(--ink-soft)" fontSize={11} allowDecimals={false} />
                <RTooltip contentStyle={TT} cursor={{ fill: "color-mix(in oklab, var(--ink-soft) 8%, transparent)" }} />
                <Bar dataKey="v" name="notifs" radius={[4, 4, 0, 0]}>
                  {notifData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel className="p-4">
          <SectionTitle sub="Par statut">Incidents</SectionTitle>
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={incData} margin={{ top: 4, right: 8, bottom: 4, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis dataKey="name" stroke="var(--ink-soft)" fontSize={11} />
                <YAxis stroke="var(--ink-soft)" fontSize={11} allowDecimals={false} />
                <RTooltip contentStyle={TT} cursor={{ fill: "color-mix(in oklab, var(--ink-soft) 8%, transparent)" }} />
                <Bar dataKey="v" name="incidents" radius={[4, 4, 0, 0]}>
                  {incData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel className="p-4">
          <SectionTitle sub="Présence actuelle">Élèves à bord</SectionTitle>
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={presData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={70} paddingAngle={2}>
                  {presData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                </Pie>
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <RTooltip contentStyle={TT} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 sm:grid-cols-3">
        <Panel className="p-4 flex items-center gap-3"><GraduationCap className="text-route" /><div><div className="text-xs text-ink-soft">Élèves sans bus</div><div className="tabular text-xl">{d.eleves.length - avecBus}</div></div></Panel>
        <Panel className="p-4 flex items-center gap-3"><Bus className="text-ok" /><div><div className="text-xs text-ink-soft">Capacité flotte</div><div className="tabular text-xl">{d.bus.reduce((s, b) => s + b.capacite, 0)}</div></div></Panel>
        <Panel className="p-4 flex items-center gap-3"><Bell className="text-line2" /><div><div className="text-xs text-ink-soft">Notifs envoyées</div><div className="tabular text-xl">{d.stats?.envoyes ?? 0}</div></div></Panel>
      </div>
    </div>
  );
}
