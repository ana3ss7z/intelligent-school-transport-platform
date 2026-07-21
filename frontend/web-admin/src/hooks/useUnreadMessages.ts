import { useEffect, useState } from "react";
import { getUnreadMessages } from "../api/endpoints";

/** Compteur de messages non-lus (badge nav), rafraîchi périodiquement. */
export function useUnreadMessages(enabled: boolean, intervalMs = 20000) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!enabled) { setCount(0); return; }
    let alive = true;
    const tick = () => getUnreadMessages().then((c) => { if (alive) setCount(c); }).catch(() => {});
    tick();
    const t = setInterval(tick, intervalMs);
    return () => { alive = false; clearInterval(t); };
  }, [enabled, intervalMs]);
  return count;
}
