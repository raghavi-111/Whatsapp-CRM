import { useEffect } from "react";
import L from "leaflet";
import { Circle, MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";

import { mappableBusinesses, searchAreaBounds } from "../utils/leadCollectorHelpers.js";

export const DEFAULT_MAP_CENTER = [20, 0];

function ViewportController({ center, radiusMeters }) {
  const map = useMap();
  useEffect(() => {
    const coordinates = searchAreaBounds(center, radiusMeters);
    const bounds = coordinates ? L.latLngBounds(coordinates) : null;
    if (!bounds) return undefined;
    let active = true;
    map.whenReady(() => {
      if (active && map.getContainer()?.isConnected) map.fitBounds(bounds, { padding: [18, 18], animate: false });
    });
    return () => { active = false; };
  }, [center[0], center[1], map, radiusMeters]);
  return null;
}

function MapPicker({ enabled, onPick }) {
  useMapEvents({ click: (event) => { if (enabled) onPick(event.latlng.lat, event.latlng.lng); } });
  return null;
}

export default function LeadCollectorMap({ center, radiusMeters, centerLabel, businesses = [], pickMode, onPick, onBusinessClick }) {
  const validCenter = Array.isArray(center) && center.length === 2 && center.every(Number.isFinite);
  const mapCenter = validCenter ? center : DEFAULT_MAP_CENTER;
  const mapped = mappableBusinesses(businesses);
  return <div className={pickMode ? "collector-map collector-map--picking" : "collector-map"}>
    <MapContainer center={mapCenter} zoom={validCenter ? 12 : 2} scrollWheelZoom>
      <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
      {validCenter && <><ViewportController center={mapCenter} radiusMeters={radiusMeters}/><Circle center={mapCenter} radius={radiusMeters} pathOptions={{ color: "#246bfd", fillColor: "#246bfd", fillOpacity: 0.09, weight: 2 }}/><Marker position={mapCenter}><Popup><strong>Search center</strong><br/>{centerLabel}<br/>Radius: {radiusMeters / 1000} km</Popup></Marker></>}
      <MapPicker enabled={pickMode} onPick={onPick}/>
      {mapped.map((item) => <Marker key={item.id} position={[Number(item.latitude), Number(item.longitude)]}><Popup><div className="map-business-popup"><strong>{item.name}</strong><span>{item.category || "Business"}{item.distance_km != null ? ` · ${Number(item.distance_km).toFixed(1)} km` : ""}</span>{item.phone && <span>{item.phone}</span>}<small>{item.address || "Location details unavailable"}</small><button type="button" onClick={(event) => onBusinessClick(item, event.currentTarget)}>View Details</button></div></Popup></Marker>)}
    </MapContainer>
  </div>;
}
