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
export function EventMap({
  lat,
  lng,
  label,
  approximate = false,
}: {
  lat: number;
  lng: number;
  label: string;
  approximate?: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    // An approximate pin is the city centroid, not the venue. Opening at street
    // zoom would draw a 14 px dot on a specific corner and assert something the
    // graph does not know; the wider view and the circle below say "in this
    // city, somewhere" instead.
    const map = L.map(container.current, {
      center: [lat, lng],
      zoom: approximate ? 12 : 15,
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
    if (approximate) {
      L.circle([lat, lng], {
        radius: 2000,
        color: "hsl(325 100% 57%)",
        weight: 1,
        fillColor: "hsl(325 100% 57%)",
        fillOpacity: 0.12,
      }).addTo(map);
    } else {
      L.marker([lat, lng], { icon, title: label }).addTo(map);
    }

    // The card animates open around us; Leaflet needs a nudge once it settled.
    const settle = window.setTimeout(() => map.invalidateSize(), 50);

    return () => {
      window.clearTimeout(settle);
      map.remove();
    };
  }, [lat, lng, label, approximate]);

  return (
    <div
      ref={container}
      role="application"
      aria-label={`Map showing ${label}`}
      className="h-48 w-full overflow-hidden rounded-md border border-border"
    />
  );
}
