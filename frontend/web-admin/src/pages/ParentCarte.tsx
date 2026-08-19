import { useEffect, useMemo, useRef, useState } from "react";
import { Radio, Clock } from "lucide-react";
import { useMyChildren } from "../hooks/useMyChildren";
import { useGpsSocket, type BusPositions } from "../hooks/useGpsSocket";
import { useTheme } from "../hooks/useTheme";
import { useTrajetRoutes } from "../hooks/useTrajetRoutes";
import { etaInputsRestants } from "../lib/routeEta";
import { predictEta, getTrajetActifBus } from "../api/endpoints";
import type { Trajet } from "../api/types";
import { MapLive } from "../components/MapLive";
import { Panel, StatusChip, Spinner } from "../components/ui";
import { EmptyState } from "../components/AsyncState";

const ECOLE = { lat: 33.893, lng: -5.5455 };

export function ParentCarte() {
  const { theme } = useTheme();
  const { enfants, mesBus, busIds, loading } = useMyChildren();
  const { positions, trails, connected } = useGpsSocket(true);
  const [etas, setEtas] = useState<Record<number, number>>({});

  // Ne garder que les bus de mes enfants
  const idSet = useMemo(() => new Set(busIds), [busIds]);
  const busesFiltres: BusPositions = useMemo(() => {
    const out: BusPositions = {};
    for (const [id, p] of Object.entries(positions)) {
      if (idSet.has(Number(id))) out[Number(id)] = p;
    }
    // repli sur la dernière position connue du bus si pas de flux live
    for (const b of mesBus) {
      if (!out[b.id] && b.latitude != null && b.longitude != null) {
        out[b.id] = { cibleType: "BUS", cibleId: b.id, latitude: b.latitude, longitude: b.longitude };
      }
    }
    return out;
  }, [positions, idSet, mesBus]);

  // Trajet actif par bus (15 s) — détermine le sens, donc la destination visée.
  const [trajets, setTrajets] = useState<Record<number, Trajet | null>>({});
  const idsKey = busIds.join(",");
  useEffect(() => {
    if (busIds.length === 0) return;
    let alive = true;
    const charger = async () => {
      const res = await Promise.all(
        busIds.map(async (id) => [id, await getTrajetActifBus(id).catch(() => null)] as const));
      if (alive) setTrajets(Object.fromEntries(res));
    };
    charger();
    const t = setInterval(charger, 15000);
    return () => { alive = false; clearInterval(t); };
  }, [idsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Tournée figée de chaque trajet → ETA mesuré LE LONG DU CIRCUIT.
  const routes = useTrajetRoutes(trajets);

  // ETA (30 s) vers la destination PERTINENTE POUR LE PARENT, sans se ré-armer
  // à chaque ping GPS. La tournée part de l'école, ramasse, puis y revient :
  //  · cible : enfant pas encore à bord → son domicile · à bord le matin → l'école · soir → domicile
  //  · chemin : distance restante SUR la tournée (à vol d'oiseau, l'ETA remonte pendant le ramassage)
  const busesRef = useRef(busesFiltres);
  busesRef.current = busesFiltres;
  const enfantsRef = useRef(enfants); enfantsRef.current = enfants;
  const trajetsRef = useRef(trajets); trajetsRef.current = trajets;
  const routesRef = useRef(routes); routesRef.current = routes;
  const [versDomicile, setVersDomicile] = useState<Record<number, boolean>>({});
  const presenceKey = enfants.map((e) => `${e.id}:${e.busId}:${e.statutPresence}`).join("|");
  // L'arrivée de la tournée change la méthode de calcul → recalculer aussitôt.
  const routesKey = busIds.map((id) => `${id}:${routes[id]?.geometrie?.length ?? 0}`).join("|");

  useEffect(() => {
    if (busIds.length === 0) return;
    let alive = true;
    const compute = async () => {
      const buses = Object.values(busesRef.current);
      if (!buses.length) return;
      const dests: Record<number, boolean> = {};
      const res = await Promise.all(buses.map(async (b) => {
        const enfant = enfantsRef.current.find((e) => e.busId === b.cibleId);
        const soir = trajetsRef.current[b.cibleId]?.sens === "SOIR";
        const vers = !!enfant && (soir || !enfant.statutPresence);
        const dest = vers && enfant.latitude != null && enfant.longitude != null
          ? { lat: enfant.latitude, lng: enfant.longitude }
          : ECOLE;
        dests[b.cibleId] = dest !== ECOLE;
        const route = routesRef.current[b.cibleId];
        try {
          // Cible = domicile (point du parcours) ou "fin" (retour école — viser les coords de
          // l'école la projetterait sur le DÉPART de la boucle).
          const inputs = route?.geometrie?.length
            ? etaInputsRestants(route.geometrie, { lat: b.latitude, lng: b.longitude },
                dest === ECOLE ? "fin" : dest, route.distancePlanM, route.dureePlanMin)
            : null;
          // `moment` = contexte trafic du modèle, pas la destination.
          const r = await predictEta(inputs
            ? { ...inputs, moment: soir ? "soir" : "matin" }
            : { bus_lat: b.latitude, bus_lng: b.longitude, dest_lat: dest.lat, dest_lng: dest.lng, moment: soir ? "soir" : "matin" });
          return [b.cibleId, r.eta_minutes] as const;
        } catch { return [b.cibleId, null] as const; }
      }));
      if (alive) {
        setVersDomicile(dests);
        setEtas(Object.fromEntries(res.filter((x): x is readonly [number, number] => x[1] != null)));
      }
    };
    compute();
    const t = setInterval(compute, 30000);
    return () => { alive = false; clearInterval(t); };
  }, [busIds.length, presenceKey, routesKey]);

  if (loading) return <Spinner label="Chargement de la carte…" />;
  if (busIds.length === 0) {
    return <Panel className="p-6"><EmptyState message="Aucun bus assigné à vos enfants pour le moment." /></Panel>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Carte de mon enfant</h1>
          <p className="text-ink-soft text-sm">Position du bus de vos enfants en temps réel.</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusChip tone={connected ? "ok" : "warn"}><Radio size={12} /> {connected ? "GPS connecté" : "hors ligne"}</StatusChip>
          {Object.keys(etas).length > 0 && (
            <StatusChip tone="line2">
              <Clock size={12} /> ETA → {Object.values(versDomicile).some(Boolean) ? "chez vous" : "école"}
            </StatusChip>
          )}
        </div>
      </div>

      <MapLive eleves={enfants} buses={busesFiltres} trails={trails} etas={etas} dark={theme === "dark"} height="72vh" />
      <p className="text-xs text-ink-soft">La carte n'affiche que le(s) bus de vos enfants.</p>
    </div>
  );
}
