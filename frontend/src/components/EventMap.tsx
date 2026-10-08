/**
 * OpenStreetMap's own embed iframe (D9) — no API key, no per-load billing.
 *
 * A card wants a still picture of one point, not a map to drive, so there is no
 * map library here: an iframe OSM already serves does the whole job, and the
 * browser owns its lifecycle across the expand/collapse the card does.
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
  // An approximate pin is the city centroid, not the venue. The 2 km circle the
  // Leaflet version drew is a wider box here: no marker, and enough frame around
  // the point that the picture says "in this city, somewhere" rather than
  // asserting a corner the graph does not know.
  const span = approximate ? 0.06 : 0.008;
  const bbox = [lng - span, lat - span, lng + span, lat + span].join(",");

  return (
    <iframe
      src={
        `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik` +
        (approximate ? "" : `&marker=${lat},${lng}`)
      }
      title={`Map showing ${label}`}
      loading="lazy"
      className="h-48 w-full overflow-hidden rounded-[16px] border border-hairline/[0.07]"
    />
  );
}
