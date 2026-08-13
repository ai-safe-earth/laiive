import L from "leaflet";
import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";

/**
 * OpenStreetMap tiles via Leaflet (D9) — no API key, no per-load billing.
 *
 * Leaflet is driven directly rather than through react-leaflet: the map mounts
 * and unmounts every time a card expands, and owning the lifecycle here keeps
 * that honest (one map instance, removed on unmount) without a wrapper library
 * whose context has to be kept in step with React versions.
 */
export function EventMap({ lat, lng, label }: { lat: number; lng: number; label: string }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const map = L.map(container.current, {
      center: [lat, lng],
      zoom: 15,
      scrollWheelZoom: false,
      attributionControl: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map);

    // The default marker icon resolves its PNGs relative to the CSS, which
    // breaks under Vite's bundling; a divIcon keeps the brand colour and needs
    // no assets at all.
    const icon = L.divIcon({
      className: "",
      html: '<div style="width:14px;height:14px;border-radius:50%;background:hsl(325 100% 57%);box-shadow:0 0 0 4px hsl(325 100% 57% / 0.35)"></div>',
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    });
    L.marker([lat, lng], { icon, title: label }).addTo(map);

    // The card animates open around us; Leaflet needs a nudge once it settled.
    const settle = window.setTimeout(() => map.invalidateSize(), 50);

    return () => {
      window.clearTimeout(settle);
      map.remove();
    };
  }, [lat, lng, label]);

  return (
    <div
      ref={container}
      role="application"
      aria-label={`Map showing ${label}`}
      className="h-48 w-full overflow-hidden rounded-md border border-border"
    />
  );
}
