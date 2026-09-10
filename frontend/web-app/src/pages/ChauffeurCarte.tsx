import { useEffect, useRef, useState } from "react";
import { Radio } from "lucide-react";
import { useMyBus } from "../hooks/useMyBus";
import { useGpsSocket, type BusPositions } from "../hooks/useGpsSocket";
import { useTheme } from "../hooks/useTheme";
import { getTournee } from "../api/endpoints";
import { MapLive, type RouteTrace } from "../components/MapLive";
import { Panel, StatusChip, Spinner } from "../components/ui";
import { EmptyState } from "../components/AsyncState";
import { lineColor } from "../lib/colors";

export function ChauffeurCarte() {
  const { theme } = useTheme();
  const { myBus, eleves, groupeId, loading } = useMyBus();
  const { positions, connected } = useGpsSocket(true);
  const [sens, setSens] = useState<"matin" | "soir">("matin");
  const [route, setRoute] = useState<RouteTrace | null>(null);

  const elevesRef = useRef(eleves);
  elevesRef.current = eleves;
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
    }).catch(() => setRoute(null));
    return () => { alive = false; };
  }, [groupeId, sens]);

  if (loading) return <Spinner label="Chargement de la carte…" />;
  if (!myBus) return <Panel className="p-6"><EmptyState message="Aucun bus ne vous est affecté." /></Panel>;

  const busPos = positions[myBus.id];
  const lat = busPos?.latitude ?? myBus.latitude ?? null;
  const lng = busPos?.longitude ?? myBus.longitude ?? null;
  const mapBuses: BusPositions = (lat != null && lng != null)
    ? { [myBus.id]: (busPos ?? { cibleType: "BUS", cibleId: myBus.id, latitude: lat, longitude: lng }) }
    : {};

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Carte — mon bus</h1>
          <p className="text-ink-soft text-sm">Bus <span className="tabular">{myBus.matricule}</span> · ma tournée</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusChip tone={connected ? "ok" : "warn"}><Radio size={12} /> {connected ? "GPS connecté" : "hors ligne"}</StatusChip>
          <select aria-label="Sens" value={sens} onChange={(e) => setSens(e.target.value as "matin" | "soir")}
            className="rounded-lg border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-route">
            <option value="matin">Matin (ramassage)</option>
            <option value="soir">Soir (dépose)</option>
          </select>
        </div>
      </div>

      <MapLive eleves={eleves} buses={mapBuses} routes={route ? [route] : []} dark={theme === "dark"} height="72vh" />
      <p className="text-xs text-ink-soft">Vue centrée sur votre bus et votre tournée uniquement.</p>
    </div>
  );
}
