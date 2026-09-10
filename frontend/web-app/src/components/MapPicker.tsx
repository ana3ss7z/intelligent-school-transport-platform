import { MapContainer, TileLayer, Marker, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const ECOLE: [number, number] = [33.893, -5.5455];

const pin = L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;border-radius:50% 50% 50% 0;background:var(--route,#2a6fdb);border:2px solid #fff;transform:rotate(-45deg);box-shadow:0 2px 5px rgba(0,0,0,.4)"></div>`,
  iconSize: [16, 16], iconAnchor: [8, 16],
});

function ClickCatcher({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({ click: (e) => onPick(e.latlng.lat, e.latlng.lng) });
  return null;
}

/** Mini-carte pour choisir des coordonnées (clic ou glisser le marqueur). */
export function MapPicker({ lat, lng, onChange, dark = false }: {
  lat: number; lng: number; onChange: (lat: number, lng: number) => void; dark?: boolean;
}) {
  const tile = dark
    ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
  const pos: [number, number] = [lat || ECOLE[0], lng || ECOLE[1]];

  return (
    <div className="rounded-lg overflow-hidden border border-line" style={{ height: 200 }}>
      <MapContainer center={pos} zoom={13} style={{ height: "100%", width: "100%" }}>
        <TileLayer url={tile} attribution="&copy; OSM &copy; CARTO" />
        <ClickCatcher onPick={onChange} />
        <Marker position={pos} icon={pin} draggable
          eventHandlers={{ dragend: (e) => { const p = e.target.getLatLng(); onChange(p.lat, p.lng); } }} />
      </MapContainer>
    </div>
  );
}
