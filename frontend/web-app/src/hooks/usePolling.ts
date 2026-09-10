import { useCallback, useEffect, useRef, useState } from "react";

interface PollingState<T> {
  data: T | null;
  loading: boolean;      // premier chargement uniquement
  refreshing: boolean;   // rafraîchissements suivants (non-bloquant)
  error: string | null;
  refetch: () => void;
  lastUpdated: number | null;
}

/**
 * Charge des données puis les rafraîchit à intervalle régulier.
 * Le 1er chargement affiche un skeleton (loading) ; les suivants sont silencieux
 * (refreshing) → pas de clignotement, l'UI reste réactive.
 * Se met en pause quand l'onglet est masqué (document.hidden).
 *
 * NB : on utilise un simple booléen `refreshing` plutôt que `useTransition`.
 * Envelopper `setData` dans une transition rend la mise à jour *concurrente* ;
 * sur les pages à sous-arbre lourd (dashboard/graphes, grandes tables) cela
 * déclenchait une erreur récupérable de rendu concurrent (React #520). Le
 * booléen évite ce chemin sans changer l'UX.
 */
export function usePolling<T>(fn: () => Promise<T>, intervalMs = 10000, deps: unknown[] = []): PollingState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const first = useRef(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback(async () => {
    if (!first.current) setRefreshing(true);
    try {
      const d = await fnRef.current();
      setData(d);
      setError(null);
      setLastUpdated(Date.now());
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { error?: string } }; message?: string })
        ?.response?.data?.error ?? (e as { message?: string })?.message ?? "Erreur";
      // On ne casse pas l'affichage existant sur un refresh raté : on garde data, on note l'erreur.
      if (first.current) setError(msg);
    } finally {
      if (first.current) { setLoading(false); first.current = false; }
      setRefreshing(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    run();
    const start = () => { timer = setInterval(() => { if (!document.hidden) run(); }, intervalMs); };
    start();
    const onVis = () => { if (!document.hidden) run(); };
    document.addEventListener("visibilitychange", onVis);
    return () => { if (timer) clearInterval(timer); document.removeEventListener("visibilitychange", onVis); };
  }, [run, intervalMs]);

  return { data, loading, refreshing, error, refetch: run, lastUpdated };
}
