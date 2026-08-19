import { useEffect, useMemo, useRef, useState } from "react";
import { Bus as BusIcon, Radio, Check, Circle, TriangleAlert, Send, Play, Flag } from "lucide-react";
import { useAsync } from "../hooks/useAsync";
import { useGpsSocket } from "../hooks/useGpsSocket";
import { useTheme } from "../hooks/useTheme";
import { useAuth } from "../auth/AuthContext";
import {
  getBus, getElevesParBus, setPresence, getTournee, predictEta, createIncident,
  demarrerTrajet, terminerTrajet, getMonTrajetActif,
} from "../api/endpoints";
import type { Bus, Eleve, TypeIncident, Trajet } from "../api/types";
import { Panel, Stat, StatusChip, Button, SectionTitle, Spinner } from "../components/ui";
import { Modal } from "../components/Modal";
import { RouteStrip } from "../components/RouteStrip";
import { MapLive, type RouteTrace } from "../components/MapLive";
import { useToast } from "../components/Toast";
import { EmptyState, ErrorState } from "../components/AsyncState";
import type { BusPositions } from "../hooks/useGpsSocket";
import { lineColor } from "../lib/colors";
import { etaInputsRestants } from "../lib/routeEta";

const ECOLE = { lat: 33.893, lng: -5.5455 };
const TYPES: TypeIncident[] = ["PANNE", "ACCIDENT", "RETARD", "ROUTE_BLOQUEE", "ABSENCE_CHAUFFEUR", "AUTRE"];
const statutTone = (s: string) => (s === "ACTIF" ? "ok" : s === "EN_PANNE" ? "alert" : "neutral");

/** Distance en mètres (haversine) — pour « prochain arrêt à ~N m ». */
const distM = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) => {
  const R = 6371000, toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat), dLng = toRad(b.lng - a.lng);
  const x = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
};
const fmtDist = (m: number) => (m < 1000 ? `~${Math.round(m / 10) * 10} m` : `~${(m / 1000).toFixed(1)} km`);

export function ChauffeurHome() {
  const { user } = useAuth();
  const { theme } = useTheme();
  const toast = useToast();
  const { positions, connected } = useGpsSocket(true);
  const { data: buses, loading, error, refetch } = useAsync(getBus, []);

  const myBus = useMemo<Bus | undefined>(
    () => (buses ?? []).find((b) => b.chauffeurId === user?.userId),
    [buses, user],
  );

  const [trajet, setTrajet] = useState<Trajet | null>(null);
  const [tripBusy, setTripBusy] = useState(false);
  const [sensChoix, setSensChoix] = useState<"matin" | "soir">("matin");
  const enCours = !!trajet;
  const sens: "matin" | "soir" = trajet ? (trajet.sens === "MATIN" ? "matin" : "soir") : sensChoix;

  const [eleves, setEleves] = useState<Eleve[]>([]);
  const [loadingEl, setLoadingEl] = useState(false);
  const [pending, setPending] = useState<number | null>(null);
  const [route, setRoute] = useState<RouteTrace | null>(null);
  const [plan, setPlan] = useState<{ distancePlanM: number | null; dureePlanMin: number | null } | null>(null);
  const [eta, setEta] = useState<number | null>(null);

  // Trajet actif du chauffeur (restauré au chargement / reload)
  useEffect(() => { getMonTrajetActif().then(setTrajet).catch(() => {}); }, []);

  // Élèves de mon bus (ordonnés)
  useEffect(() => {
    if (!myBus) return;
    setLoadingEl(true);
    getElevesParBus(myBus.id).then(setEleves).catch(() => setEleves([])).finally(() => setLoadingEl(false));
  }, [myBus]);

  // Rafraîchissement silencieux de la présence (10 s).
  // La présence change AUSSI hors de cet écran : simulateur, admin, ou le chauffeur
  // depuis un autre appareil. Sans ce rafraîchissement la liste restait figée sur son
  // état de chargement jusqu'au rechargement de la page — seuls les pointages faits
  // ICI (mise à jour optimiste) se voyaient.
  const pendingRef = useRef<number | null>(pending);
  pendingRef.current = pending;
  useEffect(() => {
    if (!myBus) return;
    const t = setInterval(async () => {
      if (document.hidden) return;
      try {
        const frais = await getElevesParBus(myBus.id);
        setEleves((actuels) => {
          const enVol = pendingRef.current;
          if (enVol == null) return frais;
          // Un pointage est encore en vol : le serveur ne le connaît pas encore,
          // on conserve la valeur optimiste pour éviter qu'elle ne « revienne ».
          const local = actuels.find((x) => x.id === enVol);
          return local ? frais.map((x) => (x.id === enVol ? local : x)) : frais;
        });
      } catch { /* réseau instable : on garde la liste courante */ }
    }, 10000);
    return () => clearInterval(t);
  }, [myBus]);

  const groupeId = eleves[0]?.groupeId ?? null;

  // Réf. des élèves pour construire les libellés d'arrêts SANS refetch la tournée à chaque pointage
  const elevesRef = useRef<Eleve[]>(eleves);
  elevesRef.current = eleves;

  // Tournée tracée (géométrie + arrêts) — ne dépend QUE du groupe et du sens (pas de la présence)
  useEffect(() => {
    if (groupeId == null) { setRoute(null); return; }
    let alive = true;
    getTournee(groupeId, sens).then((res) => {
      if (!alive) return;
      const byId = new Map(elevesRef.current.map((e) => [e.id, e]));
      const stops = ((res.ordre ?? []) as number[]).map((id, i) => {
        const e = byId.get(id);
        return e ? { n: i + 1, lat: e.latitude, lng: e.longitude, label: `${e.prenom} ${e.nom}` } : null;
      }).filter((s): s is NonNullable<typeof s> => s != null);
      setRoute({ color: lineColor(groupeId), points: (res.geometrie ?? []) as [number, number][], stops });
      // Totaux OSRM du circuit → vitesse moyenne réelle pour l'ETA restant (et figés au démarrage
      // du trajet pour que les parents calculent exactement la même chose).
      setPlan({ distancePlanM: res.distance_m ?? null, dureePlanMin: res.duree_min ?? null });
    }).catch(() => { setRoute(null); setPlan(null); });
    return () => { alive = false; };
  }, [groupeId, sens]);

  // Position du bus : live (WS) ou dernière position connue
  const busPos = myBus ? positions[myBus.id] : undefined;
  const lat = busPos?.latitude ?? myBus?.latitude ?? null;
  const lng = busPos?.longitude ?? myBus?.longitude ?? null;
  const posRef = useRef<{ lat: number | null; lng: number | null }>({ lat, lng });
  posRef.current = { lat, lng };

  // ETA de FIN DE TOURNÉE (recalcul 30 s).
  // La tournée boucle école → élèves → école : viser l'école en point-à-point donne un ETA qui
  // AUGMENTE pendant le ramassage (le bus s'en éloigne). On mesure donc ce qui reste à parcourir
  // SUR LE CIRCUIT — ça inclut tous les arrêts restants et ça décroît.
  const routeRef = useRef(route); routeRef.current = route;
  const planRef = useRef(plan); planRef.current = plan;
  useEffect(() => {
    if (!myBus) return;
    let alive = true;
    const compute = async () => {
      const p = posRef.current;
      if (p.lat == null || p.lng == null) return;
      const poly = routeRef.current?.points;
      try {
        const inputs = poly?.length
          ? etaInputsRestants(poly, { lat: p.lat, lng: p.lng }, "fin",
              planRef.current?.distancePlanM, planRef.current?.dureePlanMin)
          : null;
        // Repli point-à-point si la tournée n'est pas (encore) chargée.
        const r = await predictEta(inputs
          ? { ...inputs, moment: sens }
          : { bus_lat: p.lat, bus_lng: p.lng, dest_lat: ECOLE.lat, dest_lng: ECOLE.lng, moment: sens });
        if (alive) setEta(r.eta_minutes);
      } catch { /* ignore */ }
    };
    compute();
    const t = setInterval(compute, 30000);
    return () => { alive = false; clearInterval(t); };
  }, [myBus, sens]);

  // Trajet
  const demarrer = async () => {
    if (!myBus) return;
    setTripBusy(true);
    try {
      // On envoie la tournée figée (groupe + géométrie) → MS11 surveille la déviation pendant le trajet
      const t = await demarrerTrajet(myBus.id, sensChoix === "matin" ? "MATIN" : "SOIR",
        groupeId, route?.points, plan ?? undefined);
      setTrajet(t);
      toast.success(`Trajet ${sensChoix} démarré — l'administration est prévenue`);
    } catch (e: unknown) {
      toast.error((e as { response?: { data?: string }; message?: string })?.response?.data ?? (e as { message?: string })?.message ?? "Échec du démarrage");
    } finally { setTripBusy(false); }
  };
  const terminer = async () => {
    if (!trajet) return;
    setTripBusy(true);
    try { await terminerTrajet(trajet.id); setTrajet(null); toast.success("Trajet terminé"); }
    catch (e: unknown) { toast.error((e as { message?: string })?.message ?? "Échec"); }
    finally { setTripBusy(false); }
  };

  // Pointage : matin toggle false→true (monté) ; soir true→false (descendu)
  const pointer = async (e: Eleve) => {
    const next = !e.statutPresence;
    setPending(e.id);
    setEleves((list) => list.map((x) => (x.id === e.id ? { ...x, statutPresence: next } : x)));
    try {
      await setPresence(e.id, next);
      const verbe = sens === "matin" ? (next ? "monté" : "retiré") : (next ? "remis à bord" : "déposé");
      toast.success(`${e.prenom} ${e.nom} — ${verbe}`);
    } catch (err: unknown) {
      setEleves((list) => list.map((x) => (x.id === e.id ? { ...x, statutPresence: !next } : x)));
      toast.error((err as { message?: string })?.message ?? "Échec de la mise à jour");
    } finally { setPending(null); }
  };

  // Incident
  const [showInc, setShowInc] = useState(false);
  const [incType, setIncType] = useState<TypeIncident>("PANNE");
  const [incDesc, setIncDesc] = useState("");
  const [sending, setSending] = useState(false);
  const signaler = async () => {
    if (!myBus) return;
    setSending(true);
    try {
      await createIncident({ type: incType, busId: myBus.id, description: incDesc || undefined, latitude: lat ?? undefined, longitude: lng ?? undefined });
      toast.success("Incident signalé — l'administration est prévenue");
      setShowInc(false); setIncDesc("");
    } catch (e: unknown) {
      toast.error((e as { message?: string })?.message ?? "Échec du signalement");
    } finally { setSending(false); }
  };

  if (loading) return <Spinner label="Chargement de votre bus…" />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;
  if (!myBus) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl">Ma tournée</h1><p className="text-ink-soft text-sm">Espace chauffeur</p></div>
        <Panel className="p-6"><EmptyState message="Aucun bus ne vous est affecté. Contactez l'administration." icon={<BusIcon size={22} />} /></Panel>
      </div>
    );
  }

  // Progression : matin = montés ; soir = déposés
  const done = enCours
    ? (sens === "matin" ? eleves.filter((e) => e.statutPresence).length : eleves.filter((e) => !e.statutPresence).length)
    : 0;
  const pct = eleves.length ? Math.round((done / eleves.length) * 100) : 0;
  // Prochain arrêt : 1ᵉ élève (dans l'ordre) restant à traiter — matin : à monter ; soir : à déposer
  const prochain = enCours
    ? eleves.find((e) => (sens === "matin" ? !e.statutPresence : e.statutPresence)) ?? null
    : null;
  const distProchain = prochain && lat != null && lng != null
    ? distM({ lat, lng }, { lat: prochain.latitude, lng: prochain.longitude })
    : null;
  const mapBuses: BusPositions = (lat != null && lng != null)
    ? { [myBus.id]: (busPos ?? { cibleType: "BUS", cibleId: myBus.id, latitude: lat, longitude: lng }) }
    : {};

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Ma tournée</h1>
          <p className="text-ink-soft text-sm">Bonjour {user?.nom} — bus <span className="tabular">{myBus.matricule}</span></p>
        </div>
        <div className="flex items-center gap-2">
          <StatusChip tone={connected ? "ok" : "warn"}><Radio size={12} /> {connected ? "GPS connecté" : "hors ligne"}</StatusChip>
          <Button onClick={() => setShowInc(true)} tone="alert" variant="ghost"><TriangleAlert size={16} /> Signaler</Button>
        </div>
      </div>

      {/* Bandeau cycle de vie du trajet */}
      <Panel className="p-4 flex flex-wrap items-center gap-3">
        {enCours ? (
          <>
            <StatusChip tone="ok">● Trajet {sens} en cours</StatusChip>
            <span className="text-sm text-ink-soft">depuis {new Date(trajet!.heureDebut).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</span>
            <div className="flex-1 min-w-[160px]">
              <div className="flex justify-between text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">
                <span>{sens === "matin" ? "montés" : "déposés"}</span><span className="tabular">{done}/{eleves.length}</span>
              </div>
              <div className="h-2 rounded bg-panel-2 overflow-hidden">
                <div className="h-full rounded" style={{ width: `${pct}%`, background: "var(--ok)" }} />
              </div>
            </div>
            <Button onClick={terminer} tone="neutral" disabled={tripBusy}><Flag size={16} /> {tripBusy ? "…" : "Terminer le trajet"}</Button>
          </>
        ) : (
          <>
            <span className="text-sm text-ink-soft">Aucun trajet en cours.</span>
            <select aria-label="Sens" value={sensChoix} onChange={(e) => setSensChoix(e.target.value as "matin" | "soir")}
              className="rounded-lg border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-route">
              <option value="matin">Matin (ramassage)</option>
              <option value="soir">Soir (dépose)</option>
            </select>
            <Button onClick={demarrer} disabled={tripBusy}><Play size={16} /> {tripBusy ? "…" : "Démarrer le trajet"}</Button>
          </>
        )}
      </Panel>

      {/* KPIs */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat label="Mon bus" value={myBus.id} tone="route" hint={myBus.matricule} />
        {enCours && prochain ? (
          <Stat label="Prochain arrêt" value={`${prochain.prenom} ${prochain.nom}`}
            tone="ok" hint={distProchain != null ? `à ${fmtDist(distProchain)}` : (sens === "matin" ? "à monter" : "à déposer")} />
        ) : (
          <Stat label="Statut" value={<StatusChip tone={statutTone(myBus.statut)}>{myBus.statut}</StatusChip>} tone="ok" />
        )}
        <Stat label={sens === "matin" ? "Montés" : "Déposés"} value={`${done}/${eleves.length}`} tone="line2" hint={enCours ? "pointage en cours" : "démarrez pour pointer"} />
        <Stat label="Fin de tournée" value={eta != null ? `~${Math.round(eta)}` : "—"} unit="min" tone="warn"
          hint={route?.points?.length ? "arrêts restants inclus (MS12)" : "ETA estimé (MS12)"} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <div className="space-y-2">
          <MapLive eleves={eleves} buses={mapBuses} routes={route ? [route] : []}
            etas={eta != null ? { [myBus.id]: eta } : undefined} dark={theme === "dark"} height="55vh" />
          <p className="text-xs text-ink-soft">Astuce : lance le simulateur pour voir la position et l'ETA se mettre à jour.</p>
        </div>

        {/* Tournée + pointage */}
        <Panel className="p-4">
          <SectionTitle sub={enCours ? `${done}/${eleves.length} ${sens === "matin" ? "montés" : "déposés"}` : "Démarrez le trajet pour pointer"}>
            Tournée & pointage
          </SectionTitle>
          {loadingEl ? <Spinner /> : eleves.length === 0 ? (
            <EmptyState message="Aucun élève affecté à ce bus (clustering non appliqué ?)." />
          ) : (
            <>
              <RouteStrip eleves={eleves} color={lineColor(groupeId ?? myBus.id)} />
              <div className="mt-4 pt-3 border-t border-line">
                <div className="text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-2">
                  {enCours ? (sens === "matin" ? "Pointer les montées" : "Pointer les déposes") : "Trajet non démarré"}
                </div>
                {!enCours && <p className="text-sm text-ink-soft mb-2">Clique « Démarrer le trajet » pour activer le pointage.</p>}
                <ul className="space-y-1 max-h-[40vh] overflow-y-auto pr-1">
                  {eleves.map((e) => {
                    const isNext = enCours && prochain?.id === e.id;
                    return (
                    <li key={e.id}>
                      <button onClick={() => pointer(e)} disabled={!enCours || pending === e.id}
                        className="w-full flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm hover:bg-panel-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-left"
                        style={isNext ? { boxShadow: "inset 0 0 0 1.5px var(--route)", background: "var(--panel-2)" } : undefined}>
                        <span className="grid place-items-center size-5 rounded-full shrink-0 text-white"
                          style={{ background: e.statutPresence ? "var(--ok)" : "var(--line)" }}>
                          {e.statutPresence ? <Check size={12} /> : <Circle size={10} className="text-ink-soft" />}
                        </span>
                        <span className="tabular text-ink-soft w-6">{e.ordrePassage ?? "—"}</span>
                        <span className="flex-1 truncate">{e.prenom} {e.nom}</span>
                        {isNext && (
                          <span className="text-[10px] font-mono uppercase tracking-wider text-route shrink-0">
                            prochain{distProchain != null ? ` · ${fmtDist(distProchain)}` : ""}
                          </span>
                        )}
                        <StatusChip tone={e.statutPresence ? "ok" : "neutral"}>
                          {sens === "matin" ? (e.statutPresence ? "à bord" : "à monter") : (e.statutPresence ? "à déposer" : "déposé")}
                        </StatusChip>
                      </button>
                    </li>
                  );
                  })}
                </ul>
              </div>
            </>
          )}
        </Panel>
      </div>

      {/* Modale incident */}
      <Modal open={showInc} onClose={() => setShowInc(false)} title={`Signaler un incident — bus ${myBus.matricule}`}>
        <div className="space-y-3">
          <div>
            <label htmlFor="inc-type" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Type</label>
            <select id="inc-type" value={incType} onChange={(e) => setIncType(e.target.value as TypeIncident)}
              className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route">
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="inc-desc" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Description</label>
            <textarea id="inc-desc" value={incDesc} onChange={(e) => setIncDesc(e.target.value)} rows={3}
              placeholder="Décris brièvement la situation…"
              className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-route resize-none" />
          </div>
          <p className="text-xs text-ink-soft">Ta position actuelle est jointe automatiquement si le GPS est actif.</p>
          <div className="flex justify-end gap-2 pt-1">
            <Button onClick={() => setShowInc(false)} tone="neutral" variant="ghost">Annuler</Button>
            <Button onClick={signaler} tone="alert" disabled={sending}><Send size={16} /> {sending ? "Envoi…" : "Signaler"}</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
