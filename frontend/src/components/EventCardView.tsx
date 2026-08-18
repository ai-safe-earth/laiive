import type { EventCard } from "@shared/protocol";
import { ExternalLink, Info, MapPin, Ticket } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";
import { EventMap } from "./EventMap";

/** "sáb 15 nov, 21:00" in the user's language, or null when the date is absent. */
function formatWhen(
  startAt: string | null | undefined,
  language: string,
  timeKnown: boolean,
): string | null {
  if (!startAt) return null;
  const date = new Date(startAt);
  if (Number.isNaN(date.getTime())) return startAt;
  // A listing that gave only a date parses to midnight upstream. Printing
  // "00:00" would turn that default into a claim about when the doors open.
  const time = timeKnown ? ({ hour: "2-digit", minute: "2-digit" } as const) : {};
  return new Intl.DateTimeFormat(language, {
    weekday: "short",
    day: "numeric",
    month: "short",
    ...time,
  }).format(date);
}

function formatPrice(card: EventCard, free: string): string | null {
  const { price_min: min, price_max: max, price_currency: currency } = card;
  if (min === null || min === undefined) return null;
  const unit = currency ?? "EUR";
  const money = (value: number) =>
    new Intl.NumberFormat(undefined, { style: "currency", currency: unit }).format(value);
  if (min === 0 && (max === null || max === undefined || max === 0)) return free;
  if (max === null || max === undefined || max === min) return money(min);
  return `${money(min)} – ${money(max)}`;
}

export function EventCardView({ card, language }: { card: EventCard; language: string }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [showMap, setShowMap] = useState(false);
  const [showProvenance, setShowProvenance] = useState(false);

  // Rows written before the flag existed have no value and keep the old
  // behaviour, which was right for every seed event.
  const when = formatWhen(card.start_at, language, card.start_time_known !== false);
  const price = formatPrice(card, t.cards.free);
  const hasCoordinates =
    typeof card.lat === "number" && typeof card.lng === "number";
  // The pin is the city's centre, not the venue's door. Say so, and send the
  // "open in Maps" link to the venue's name instead of to coordinates we know
  // are only approximately right.
  const approximate = card.geocode_precision === "city_centroid";
  const place = [card.venue, card.city].filter(Boolean).join(", ");
  // Swept from a listing page rather than submitted by whoever is putting the
  // night on. Seed rows are ours and pro_submission rows came from a promoter.
  const fromSearch = card.source !== "seed" && card.source !== "pro_submission";
  // What this card is actually missing, read off the card — never a guess about
  // why. An empty list is normal: a swept listing can be complete.
  const notStated = [
    card.start_time_known === false && t.cards.fieldTime,
    card.price_min === null || card.price_min === undefined ? t.cards.fieldPrice : null,
    card.geocode_precision === "city_centroid" && t.cards.fieldLocation,
  ].filter(Boolean) as string[];
  const mapsQuery = approximate
    ? encodeURIComponent(place || card.name)
    : `${card.lat},${card.lng}`;

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
        {fromSearch && (
          <button
            type="button"
            onClick={() => setShowProvenance(!showProvenance)}
            aria-expanded={showProvenance}
            aria-label={t.cards.webAria}
            // A title attribute is a hover, and a phone has no hover — the
            // explanation has to be reachable by tapping.
            className="flex shrink-0 items-center gap-1 rounded bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground transition-colors hover:text-primary"
          >
            {t.cards.web}
            <Info className="h-3 w-3" />
          </button>
        )}
      </header>

      {showProvenance && (
        <p className="pt-2 text-xs leading-relaxed text-muted-foreground">
          {t.cards.webTitle}
          {notStated.length > 0 && ` ${t.cards.webMissing}: ${notStated.join(", ")}.`}
        </p>
      )}

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
          <EventMap
            lat={card.lat as number}
            lng={card.lng as number}
            label={place || card.name}
            approximate={approximate}
          />
          {approximate && (
            <p className="text-xs text-muted-foreground">{t.cards.approximate}</p>
          )}
          <a
            href={`https://www.google.com/maps/search/?api=1&query=${mapsQuery}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
          >
            {t.cards.openMaps} <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      )}

      <footer className="flex flex-wrap items-center gap-3 pt-3 text-xs">
        {card.description && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-muted-foreground/80 transition-colors hover:text-primary"
          >
            {expanded ? t.cards.less : t.cards.readMore}
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
            {showMap ? t.cards.hideMap : t.cards.map}
          </button>
        )}
        {card.ticket_url && (
          <a
            href={card.ticket_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            <Ticket className="h-3 w-3" /> {t.cards.tickets}
          </a>
        )}
      </footer>
    </article>
  );
}
