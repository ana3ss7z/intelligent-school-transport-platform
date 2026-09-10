import { MapContainer, TileLayer, CircleMarker, Marker, Polygon, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo } from "react";
import type { Eleve } from "../api/types";
import { lineColor } from "../lib/colors";
import { convexHull, centroid, padPoly, type LatLng } from "../lib/hull";

const ECOLE: LatLng = [33.893, -5.5455];

function schoolIcon() {
  return L.divIcon({
    className: "",
    html: `<div style="display:grid;place-items:center;width:28px;height:28px;border-radius:8px;background:#0e2a47;font-size:15px;box-shadow:0 2px 6px rgba(0,0,0,.35);border:2px solid #fff">🏫</div>`,
    iconSize: [28, 28], iconAnchor: [14, 14],
  });
}
function labelIcon(text: string, color: string) {
  return L.divIcon({
    className: "",
    html: `<div style="transform:translate(-50%,-50%);font:700 11px/1 'JetBrains Mono Variable',monospace;padding:1px 7px;border-radius:7px;background:rgba(11,13,18,.82);border:1px solid ${color};color:${color};white-space:nowrap">${text}</div>`,
    iconSize: [0, 0],
  });
}

/** Recadre la carte sur tous les points à l'ouverture. */
function FitBounds({ points }: { points: LatLng[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length) map.fitBounds(L.latLngBounds(points), { padding: [30, 30] });
    setTimeout(() => map.invalidateSize(), 60);
  }, [map, points]);
  return null;
}

export interface ClusterGroup { g: number; color: string; count: number; noise: boolean }

/** Calcule les groupes (couleur + effectif) pour la légende/filtres. */
export function computeGroups(eleves: Eleve[]): ClusterGroup[] {
  const map = new Map<number, number>();
  for (const e of eleves) if (e.groupeId != null) map.set(e.groupeId, (map.get(e.groupeId) ?? 0) + 1);
  return [...map.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([g, count]) => ({ g, color: g === 999 ? "#64748b" : lineColor(g), count, noise: g === 999 }));
}

export function ClusterMap({
  eleves, hidden, showHull = true, showPts = true, dark = false, height = "60vh",
}: {
  eleves: Eleve[];
  hidden: Set<number>;
  showHull?: boolean;
  showPts?: boolean;
  dark?: boolean;
  height?: string;
}) {
  const tile = dark
    ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

  const groups = useMemo(() => {
    const byG = new Map<number, Eleve[]>();
    for (const e of eleves) {
      if (e.latitude == null || e.longitude == null || e.groupeId == null) continue;
      const arr = byG.get(e.groupeId);
      if (arr) arr.push(e); else byG.set(e.groupeId, [e]);
    }
    return [...byG.entries()].sort((a, b) => a[0] - b[0]).map(([g, arr]) => {
      const pts = arr.map((e) => [e.latitude, e.longitude] as LatLng);
      const c = centroid(pts);
      const color = g === 999 ? "#64748b" : lineColor(g);
      return { g, arr, pts, c, color, noise: g === 999 };
    });
  }, [eleves]);

  const allPts = useMemo(
    () => [ECOLE, ...groups.filter((gr) => !hidden.has(gr.g)).flatMap((gr) => gr.pts)],
    [groups, hidden],
  );

  return (
    <div className="rounded-xl overflow-hidden border border-line" style={{ height }}>
      <MapContainer center={ECOLE} zoom={13} style={{ height: "100%", width: "100%" }} preferCanvas>
        <TileLayer url={tile} attribution="&copy; OpenStreetMap &copy; CARTO" />
        <FitBounds points={allPts} />

        {groups.map((gr) => {
          if (hidden.has(gr.g)) return null;
          return (
            <div key={gr.g}>
              {showHull && gr.pts.length >= 3 && !gr.noise && (
                <Polygon positions={padPoly(convexHull(gr.pts), gr.c, 1.12)}
                  pathOptions={{ color: gr.color, weight: 2, opacity: 0.75, fillColor: gr.color, fillOpacity: 0.16 }} />
              )}
              {showPts && gr.arr.map((e) => (
                <CircleMarker key={e.id} center={[e.latitude, e.longitude]} radius={4}
                  pathOptions={{ color: "#0b0d12", weight: 1, fillColor: gr.color, fillOpacity: 0.95 }}>
                  <Tooltip>{e.prenom} {e.nom} · {gr.noise ? "dispersé" : `groupe ${gr.g}`}</Tooltip>
                </CircleMarker>
              ))}
              <Marker position={gr.c} interactive={false}
                icon={labelIcon(`${gr.noise ? "dispersés" : "G" + gr.g} · ${gr.arr.length}`, gr.color)} />
            </div>
          );
        })}

        <Marker position={ECOLE} icon={schoolIcon()}>
          <Tooltip>École Al Massira</Tooltip>
        </Marker>
      </MapContainer>
    </div>
  );
}
