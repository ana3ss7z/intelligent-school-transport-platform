import { MapContainer, TileLayer, CircleMarker, Marker, Polyline, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-polylinedecorator";
import { useEffect, useMemo, useRef } from "react";
import type { Eleve, GpsPosition } from "../api/types";
import type { BusPositions, BusTrails } from "../hooks/useGpsSocket";
import { lineColor } from "../lib/colors";

const ECOLE: [number, number] = [33.893, -5.5455];

export interface Stop { n: number; lat: number; lng: number; label: string }
export interface RouteTrace { color: string; points: [number, number][]; stops?: Stop[] }

const prefersReduced = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function busIconHtml(color: string, label: string, anomaly: boolean) {
  const pulse = anomaly ? "pulse-alert" : "";
  const border = anomaly ? "var(--alert)" : "#fff";
  return `<div class="${pulse}" style="display:grid;place-items:center;width:26px;height:26px;border-radius:8px;background:${color};color:#fff;font:600 11px/1 'JetBrains Mono Variable',monospace;box-shadow:0 2px 6px rgba(0,0,0,.35);border:2px solid ${border}">${label}</div>`;
}

function stopIcon(color: string, n: number) {
  return L.divIcon({
    className: "",
    html: `<div style="display:grid;place-items:center;width:22px;height:22px;border-radius:50%;background:#fff;color:${color};font:700 11px/1 'JetBrains Mono Variable',monospace;box-shadow:0 1px 5px rgba(0,0,0,.35);border:2.5px solid ${color}">${n}</div>`,
    iconSize: [22, 22], iconAnchor: [11, 11],
  });
}

function schoolIcon() {
  return L.divIcon({
    className: "",
    html: `<div style="display:grid;place-items:center;width:28px;height:28px;border-radius:8px;background:#0e2a47;font-size:15px;box-shadow:0 2px 6px rgba(0,0,0,.35);border:2px solid #fff">🏫</div>`,
    iconSize: [28, 28], iconAnchor: [14, 14],
  });
}

/** Marqueur bus qui GLISSE vers sa nouvelle position (rAF) au lieu de sauter. */
function AnimatedBus({ pos, color, anomaly, eta }: { pos: GpsPosition; color: string; anomaly: boolean; eta?: number }) {
  const map = useMap();
  const markerRef = useRef<L.Marker | null>(null);
  const rafRef = useRef<number | null>(null);

  // Création unique du marqueur natif
  useEffect(() => {
    const m = L.marker([pos.latitude, pos.longitude], {
      icon: L.divIcon({ className: "", html: busIconHtml(color, String(pos.cibleId), anomaly), iconSize: [26, 26], iconAnchor: [13, 13] }),
      zIndexOffset: 500,
    }).addTo(map);
    m.bindTooltip("", { direction: "top" });
    markerRef.current = m;
    return () => { map.removeLayer(m); markerRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);

  // Icône (couleur / anomalie) + tooltip
  useEffect(() => {
    const m = markerRef.current; if (!m) return;
    m.setIcon(L.divIcon({ className: "", html: busIconHtml(color, String(pos.cibleId), anomaly), iconSize: [26, 26], iconAnchor: [13, 13] }));
    m.setTooltipContent(
      `Bus ${pos.cibleId}`
      + (pos.vitesse != null ? ` · ${Math.round(pos.vitesse)} km/h` : "")
      + (eta != null ? ` · ~${Math.round(eta)} min → école` : "")
      + (anomaly ? " · ⚠ anomalie" : ""),
    );
  }, [color, anomaly, eta, pos.cibleId, pos.vitesse]);

  // Animation vers la nouvelle cible
  useEffect(() => {
    const m = markerRef.current; if (!m) return;
    const to = L.latLng(pos.latitude, pos.longitude);
    if (prefersReduced()) { m.setLatLng(to); return; }
    const from = m.getLatLng();
    const dur = 900, t0 = performance.now();
    const step = (now: number) => {
      const k = Math.min(1, (now - t0) / dur);
      m.setLatLng([from.lat + (to.lat - from.lat) * k, from.lng + (to.lng - from.lng) * k]);
      if (k < 1) rafRef.current = requestAnimationFrame(step);
    };
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(step);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [pos.latitude, pos.longitude]);

  return null;
}

/** Flèches de sens le long d'une polyligne. */
function ArrowDecorator({ positions, color }: { positions: [number, number][]; color: string }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length < 2) return;
    const line = L.polyline(positions);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Ls = L as any;
    const deco = Ls.polylineDecorator(line, {
      patterns: [{ offset: 30, repeat: 90,
        symbol: Ls.Symbol.arrowHead({ pixelSize: 11, polygon: false, pathOptions: { stroke: true, color, weight: 3, opacity: 0.95 } }) }],
    }).addTo(map);
    return () => { map.removeLayer(deco); };
  }, [map, positions, color]);
  return null;
}

export function MapLive({
  eleves = [], buses = {}, trails = {}, routes = [], anomalyBusIds, etas, dark = false, height = "70vh",
}: {
  eleves?: Eleve[];
  buses?: BusPositions;
  trails?: BusTrails;
  routes?: RouteTrace[];
  anomalyBusIds?: Set<number>;
  etas?: Record<number, number>;
  dark?: boolean;
  height?: string;
}) {
  const tile = dark
    ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

  const hasRoute = routes.length > 0;
  const pts = useMemo(() => eleves.filter((e) => e.latitude != null && e.longitude != null), [eleves]);

  return (
    <div className="rounded-xl overflow-hidden border border-line" style={{ height }}>
      <MapContainer center={ECOLE} zoom={13} style={{ height: "100%", width: "100%" }} preferCanvas>
        <TileLayer url={tile} attribution="&copy; OpenStreetMap &copy; CARTO" />

        <Marker position={ECOLE} icon={schoolIcon()}>
          <Tooltip>École Al Massira (dépôt · départ & arrivée)</Tooltip>
        </Marker>

        {/* Élèves — estompés quand une tournée est tracée */}
        {pts.map((e) => (
          <CircleMarker key={e.id} center={[e.latitude, e.longitude]} radius={hasRoute ? 3 : 4}
            pathOptions={{ color: lineColor(e.groupeId), fillColor: lineColor(e.groupeId),
              fillOpacity: hasRoute ? 0.25 : 0.85, weight: 1, opacity: hasRoute ? 0.3 : 1 }}>
            <Tooltip>{e.prenom} {e.nom}{e.groupeId ? ` · groupe ${e.groupeId}` : ""}</Tooltip>
          </CircleMarker>
        ))}

        {/* Traînées GPS des bus */}
        {Object.entries(trails).map(([id, path]) =>
          path.length > 1 ? (
            <Polyline key={`trail-${id}`} positions={path}
              pathOptions={{ color: lineColor(Number(id)), weight: 2.5, opacity: 0.35, dashArray: "1 6", lineCap: "round" }} />
          ) : null,
        )}

        {/* Tournées : tracé OSRM + flèches + arrêts numérotés */}
        {routes.map((r, i) => (
          <div key={i}>
            <Polyline positions={r.points} pathOptions={{ color: r.color, weight: 4, opacity: 0.9 }} />
            <ArrowDecorator positions={r.points} color={r.color} />
            {r.stops?.map((s) => (
              <Marker key={s.n} position={[s.lat, s.lng]} icon={stopIcon(r.color, s.n)} zIndexOffset={1000}>
                <Tooltip><span className="font-mono">#{s.n}</span> · {s.label}</Tooltip>
              </Marker>
            ))}
          </div>
        ))}

        {/* Bus — marqueurs animés (glissent) + pulse si anomalie */}
        {Object.values(buses).map((b) => (
          <AnimatedBus key={b.cibleId} pos={b} color={lineColor(b.cibleId)}
            anomaly={!!anomalyBusIds?.has(b.cibleId)} eta={etas?.[b.cibleId]} />
        ))}
      </MapContainer>
    </div>
  );
}
