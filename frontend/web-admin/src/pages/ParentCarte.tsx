import { useEffect, useMemo, useRef, useState } from "react";
import { Radio, Clock } from "lucide-react";
import { useMyChildren } from "../hooks/useMyChildren";
import { useGpsSocket, type BusPositions } from "../hooks/useGpsSocket";
import { useTheme } from "../hooks/useTheme";
import { predictEta } from "../api/endpoints";
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

  // ETA bus → école (30 s), sans se ré-armer à chaque ping GPS
  const busesRef = useRef(busesFiltres);
  busesRef.current = busesFiltres;
  useEffect(() => {
    if (busIds.length === 0) return;
    let alive = true;
    const compute = async () => {
      const buses = Object.values(busesRef.current);
      if (!buses.length) return;
      const res = await Promise.all(buses.map(async (b) => {
        try {
          const r = await predictEta({ bus_lat: b.latitude, bus_lng: b.longitude, dest_lat: ECOLE.lat, dest_lng: ECOLE.lng, moment: "matin" });
          return [b.cibleId, r.eta_minutes] as const;
        } catch { return [b.cibleId, null] as const; }
      }));
      if (alive) setEtas(Object.fromEntries(res.filter((x): x is readonly [number, number] => x[1] != null)));
    };
    compute();
    const t = setInterval(compute, 30000);
    return () => { alive = false; clearInterval(t); };
  }, [busIds.length]);

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
          {Object.keys(etas).length > 0 && <StatusChip tone="line2"><Clock size={12} /> ETA → école</StatusChip>}
        </div>
      </div>

      <MapLive eleves={enfants} buses={busesFiltres} trails={trails} etas={etas} dark={theme === "dark"} height="72vh" />
      <p className="text-xs text-ink-soft">La carte n'affiche que le(s) bus de vos enfants.</p>
    </div>
  );
}
