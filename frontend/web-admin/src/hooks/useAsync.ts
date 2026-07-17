import { useCallback, useEffect, useState } from "react";

interface State<T> { data: T | null; loading: boolean; error: string | null; }

/** Petit hook de chargement de données avec refetch et gestion d'erreur. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<State<T>>({ data: null, loading: true, error: null });

  const run = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((e) => setState({ data: null, loading: false, error: e?.response?.data?.error ?? e?.message ?? "Erreur" }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { run(); }, [run]);
  return { ...state, refetch: run };
}
