import { useMemo } from "react";
import { useAsync } from "./useAsync";
import { useAuth } from "../auth/AuthContext";
import { getBus, getElevesParParent } from "../api/endpoints";
import type { Bus, Eleve } from "../api/types";

/** Résout les enfants du parent connecté + les bus associés. */
export function useMyChildren() {
  const { user } = useAuth();
  const parentId = user?.userId ?? 0;
  const { data: eleves, loading: le, error, refetch } = useAsync<Eleve[]>(
    () => (parentId ? getElevesParParent(parentId) : Promise.resolve([])),
    [parentId],
  );
  const { data: buses, loading: lb } = useAsync(getBus, []);

  const busById = useMemo(() => new Map((buses ?? []).map((b) => [b.id, b])), [buses]);
  const enfants = eleves ?? [];
  const busIds = useMemo(
    () => [...new Set(enfants.map((e) => e.busId).filter((b): b is number => b != null))],
    [enfants],
  );
  const mesBus = useMemo<Bus[]>(
    () => busIds.map((id) => busById.get(id)).filter((b): b is Bus => b != null),
    [busIds, busById],
  );

  return { enfants, busById, busIds, mesBus, loading: le || lb, error, refetch };
}
