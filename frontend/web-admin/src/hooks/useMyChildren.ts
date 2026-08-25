import { useMemo } from "react";
import { useAsync } from "./useAsync";
import { usePolling } from "./usePolling";
import { useAuth } from "../auth/AuthContext";
import { getBus, getElevesParParent } from "../api/endpoints";
import type { Bus, Eleve } from "../api/types";
import { useParams } from "../params/ParamsContext";

/**
 * Résout les enfants du parent connecté + les bus associés.
 *
 * Les enfants sont **sondés** (20 s, silencieux) et non chargés une seule fois : `statutPresence`
 * change côté serveur quand le chauffeur pointe la montée. Sans ce sondage, la pastille
 * « à bord » et le compte à rebours (dont la destination dépend de la présence) restaient figés
 * jusqu'au rechargement de la page.
 */
export function useMyChildren() {
  const { ui } = useParams();   // intervalles de sondage pilotés depuis la page Paramètres
  const { user } = useAuth();
  const parentId = user?.userId ?? 0;
  const { data: eleves, loading: le, error, refetch } = usePolling<Eleve[]>(
    () => (parentId ? getElevesParParent(parentId) : Promise.resolve([])),
    ui.pollTrajetMs,
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
