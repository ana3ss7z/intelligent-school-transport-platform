import { useEffect, useRef, useState } from "react";
import type { GpsPosition } from "../api/types";

const WS_URL = import.meta.env.VITE_WS_GPS ?? "ws://localhost:8083/ws/gps";

export type BusPositions = Record<number, GpsPosition>;
export type BusTrails = Record<number, [number, number][]>;

const TRAIL_MAX = 25; // nb de points conservés par bus pour la traînée

/**
 * Flux GPS temps réel (MS3). Agrège les positions par busId.
 * Throttle d'état (~1 s) pour éviter les re-renders en rafale (perf, cf. react-best-practices).
 * Reconnexion auto ; `connected` reflète l'état du socket.
 */
export function useGpsSocket(enabled = true) {
  const [positions, setPositions] = useState<BusPositions>({});
  const [trails, setTrails] = useState<BusTrails>({});
  const [connected, setConnected] = useState(false);
  const bufferRef = useRef<BusPositions>({});
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let ws: WebSocket | null = null;
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | null = null;

    const flush = () => {
      const batch = bufferRef.current;
      setPositions((prev) => ({ ...prev, ...batch }));
      setTrails((prev) => {
        const next = { ...prev };
        for (const [id, p] of Object.entries(batch)) {
          const key = Number(id);
          const pt: [number, number] = [p.latitude, p.longitude];
          const arr = next[key] ? [...next[key], pt] : [pt];
          next[key] = arr.length > TRAIL_MAX ? arr.slice(-TRAIL_MAX) : arr;
        }
        return next;
      });
      bufferRef.current = {};
      rafRef.current = null;
    };

    const connect = () => {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => { setConnected(true); ws?.send(JSON.stringify({ subscribe: "ALL" })); };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(connect, 2500);
      };
      ws.onerror = () => ws?.close();
      ws.onmessage = (ev) => {
        try {
          const p = JSON.parse(ev.data) as GpsPosition;
          if (p?.cibleType === "BUS" && p.cibleId != null) {
            bufferRef.current[p.cibleId] = p;
            if (rafRef.current == null) rafRef.current = window.setTimeout(flush, 1000);
          }
        } catch { /* message non-JSON ignoré */ }
      };
    };
    connect();

    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      if (rafRef.current) clearTimeout(rafRef.current);
      ws?.close();
    };
  }, [enabled]);

  return { positions, trails, connected };
}
