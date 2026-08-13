import type { EventCard } from "@shared/protocol";
import { ExternalLink, MapPin, Ticket } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { EventMap } from "./EventMap";

/** "sáb 15 nov, 21:00" in the user's language, or null when the date is absent. */
function formatWhen(startAt: string | null | undefined, language: string): string | null {
  if (!startAt) return null;
  const date = new Date(startAt);
  if (Number.isNaN(date.getTime())) return startAt;
  return new Intl.DateTimeFormat(language, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatPrice(card: EventCard): string | null {
  const { price_min: min, price_max: max, price_currency: currency } = card;
  if (min === null || min === undefined) return null;
  const unit = currency ?? "EUR";
  const money = (value: number) =>
    new Intl.NumberFormat(undefined, { style: "currency", currency: unit }).format(value);
  if (min === 0 && (max === null || max === undefined || max === 0)) return "free";
  if (max === null || max === undefined || max === min) return money(min);
  return `${money(min)} – ${money(max)}`;
}

export function EventCardView({ card, language }: { card: EventCard; language: string }) {
  const [expanded, setExpanded] = useState(false);
  const [showMap, setShowMap] = useState(false);

  const when = formatWhen(card.start_at, language);
  const price = formatPrice(card);
  const hasCoordinates =
    typeof card.lat === "number" && typeof card.lng === "number";
  const place = [card.venue, card.city].filter(Boolean).join(", ");

  return (
    <article className="rounded-lg border border-border/50 bg-card p-3 transition-colors hover:border-primary/30 sm:p-4">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="truncate font-ibm-plex text-base font-semibold text-foreground">
            {card.name}
          </h4>
          {card.artists.length > 0 && (
            <p className="truncate text-sm text-muted-foreground">{card.artists.join(", ")}</p>
          )}
        </div>
        {card.source !== "seed" && card.source !== "pro_submission" && (
          <span
            className="shrink-0 rounded bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground"
            title="Found on the internet, not submitted by the promoter"
          >
            web
          </span>
        )}
      </header>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-2 text-sm">
        {place && <span className="text-muted-foreground">{place}</span>}
        {when && <span className="text-muted-foreground">{when}</span>}
        {price && <span className="font-medium text-primary">{price}</span>}
        {typeof card.distance_km === "number" && (
          <span className="text-muted-foreground">{card.distance_km.toFixed(1)} km</span>
        )}
      </div>

      {expanded && card.description && (
        <p className="whitespace-pre-wrap pt-2 text-sm text-muted-foreground">
          {card.description}
        </p>
      )}

      {showMap && hasCoordinates && (
        <div className="space-y-1 pt-3">
          <EventMap lat={card.lat as number} lng={card.lng as number} label={place || card.name} />
          <a
            href={`https://www.google.com/maps/search/?api=1&query=${card.lat},${card.lng}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
          >
            open in Google Maps <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      )}

      <footer className="flex flex-wrap items-center gap-3 pt-3 text-xs">
        {card.description && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-muted-foreground/80 transition-colors hover:text-primary"
          >
            {expanded ? "− less" : "+ read more"}
          </button>
        )}
        {hasCoordinates && (
          <button
            onClick={() => setShowMap(!showMap)}
            className={cn(
              "inline-flex items-center gap-1 transition-colors hover:text-primary",
              showMap ? "text-primary" : "text-muted-foreground/80",
            )}
          >
            <MapPin className="h-3 w-3" />
            {showMap ? "hide map" : "map"}
          </button>
        )}
        {card.ticket_url && (
          <a
            href={card.ticket_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            <Ticket className="h-3 w-3" /> tickets
          </a>
        )}
      </footer>
    </article>
  );
}
