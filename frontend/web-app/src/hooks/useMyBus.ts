import { useMemo } from "react";
import { useAsync } from "./useAsync";
import { useAuth } from "../auth/AuthContext";
import { getBus, getElevesParBus } from "../api/endpoints";
import type { Bus, Eleve } from "../api/types";

/** Résout le bus du chauffeur connecté (bus.chauffeurId === userId) + ses élèves ordonnés. */
export function useMyBus() {
  const { user } = useAuth();
  const { data: buses, loading: lb, error } = useAsync(getBus, []);
  const myBus = useMemo<Bus | undefined>(
    () => (buses ?? []).find((b) => b.chauffeurId === user?.userId),
    [buses, user],
  );
  const busId = myBus?.id ?? 0;
  const { data: eleves, loading: le, refetch } = useAsync<Eleve[]>(
    () => (busId ? getElevesParBus(busId) : Promise.resolve([])),
    [busId],
  );
  const groupeId = eleves?.[0]?.groupeId ?? null;
  return { myBus, eleves: eleves ?? [], groupeId, loading: lb || le, error, refetch };
}
