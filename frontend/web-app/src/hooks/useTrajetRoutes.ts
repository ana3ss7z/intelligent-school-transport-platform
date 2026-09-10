import { useEffect, useRef, useState } from "react";
import { getTrajetRoute, type TrajetRoute } from "../api/endpoints";
import type { Trajet } from "../api/types";

/**
 * Tournées figées des trajets en cours, par busId.
 *
 * Rechargées uniquement quand un trajet démarre / se termine / change (clé = ids de trajet),
 * pas au rythme du sondage des trajets : la polyligne pèse plusieurs dizaines de Ko.
 */
export function useTrajetRoutes(trajets: Record<number, Trajet | null>) {
  const [routes, setRoutes] = useState<Record<number, TrajetRoute | null>>({});
  const trajetsRef = useRef(trajets);
  trajetsRef.current = trajets;

  const key = Object.entries(trajets)
    .map(([busId, t]) => `${busId}:${t?.id ?? "-"}`)
    .sort()
    .join("|");

  useEffect(() => {
    const ids = Object.entries(trajetsRef.current)
      .filter(([, t]) => t != null)
      .map(([busId]) => Number(busId));
    if (ids.length === 0) { setRoutes({}); return; }
    let alive = true;
    Promise.all(ids.map(async (id) => [id, await getTrajetRoute(id).catch(() => null)] as const))
      .then((res) => { if (alive) setRoutes(Object.fromEntries(res)); });
    return () => { alive = false; };
  }, [key]);

  return routes;
}
