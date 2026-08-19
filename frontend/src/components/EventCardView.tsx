import type { EventCard } from "@shared/protocol";
import { useState } from "react";
import { Icon } from "@/components/Icon";
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

/**
 * A pill sized as the brand draws it (11.5px, ~30px tall) but with a 44px
 * touch target underneath — the artwork's spacing and the accessibility floor
 * both hold, which they do not if the pill is simply grown to 44px.
 */
const PILL =
  "relative inline-flex items-center rounded-full px-3 py-[9px] text-[11.5px] font-medium leading-none " +
  "transition-colors after:absolute after:inset-x-0 after:-top-[7px] after:h-11 after:content-['']";

export function EventCardView({ card, language }: { card: EventCard; language: string }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [showMap, setShowMap] = useState(false);
  const [showProvenance, setShowProvenance] = useState(false);

  // Rows written before the flag existed have no value and keep the old
  // behaviour, which was right for every seed event.
  const when = formatWhen(card.start_at, language, card.start_time_known !== false);
  const price = formatPrice(card, t.cards.free);
  const isFree = price === t.cards.free;
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

  const meta = [place, when, typeof card.distance_km === "number" ? `${card.distance_km.toFixed(1)} km` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <article className="rounded-[20px] border border-hairline/[0.07] bg-card px-[15px] py-[13px]">
      <header className="flex items-baseline justify-between gap-2">
        <h4 className="min-w-0 font-bebas text-[18px] leading-[1.05] tracking-[0.03em] text-card-foreground">
          {card.name}
        </h4>
        {price && (
          <span
            className={cn(
              "flex-none rounded-full px-[9px] py-[5px] text-[11px] font-bold leading-none text-primary-foreground",
              // Free is the one thing fuchsia says besides the brand itself.
              isFree ? "bg-primary" : "bg-secondary",
            )}
          >
            {isFree ? price.toUpperCase() : price}
          </span>
        )}
      </header>

      {card.artists.length > 0 && (
        <p className="truncate pt-1 text-[12.5px] leading-[1.45] text-muted-foreground">
          {card.artists.join(", ")}
        </p>
      )}
      {meta && (
        <p className="pt-1 text-[12.5px] leading-[1.45] text-muted-foreground">{meta}</p>
      )}

      {fromSearch && (
        <button
          type="button"
          onClick={() => setShowProvenance(!showProvenance)}
          aria-expanded={showProvenance}
          aria-label={t.cards.webAria}
          // A title attribute is a hover, and a phone has no hover — the
          // explanation has to be reachable by tapping.
          className="mt-2 rounded-full border border-field-border px-2.5 py-1 font-mono text-[9.5px] uppercase tracking-[0.11em] text-ink-dim transition-colors hover:text-foreground"
        >
          {t.cards.web}
        </button>
      )}

      {showProvenance && (
        <p className="pt-2 text-[12.5px] leading-[1.45] text-muted-foreground">
          {t.cards.webTitle}
          {notStated.length > 0 && ` ${t.cards.webMissing}: ${notStated.join(", ")}.`}
        </p>
      )}

      {expanded && card.description && (
        <p className="whitespace-pre-wrap pt-2 text-[12.5px] leading-[1.5] text-muted-foreground">
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
            <p className="text-[12.5px] leading-[1.45] text-muted-foreground">
              {t.cards.approximate}
            </p>
          )}
          <a
            href={`https://www.google.com/maps/search/?api=1&query=${mapsQuery}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[12.5px] text-muted-foreground transition-colors hover:text-foreground"
          >
            {t.cards.openMaps}
            <Icon name="share" className="h-3.5 w-3.5" />
          </a>
        </div>
      )}

      <footer className="flex flex-wrap items-center gap-2 pt-2.5">
        {card.description && (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className={cn(PILL, "bg-field-border text-white hover:bg-muted")}
          >
            {expanded ? t.cards.less : t.cards.readMore}
          </button>
        )}
        {hasCoordinates && (
          <button
            type="button"
            onClick={() => setShowMap(!showMap)}
            className={cn(
              PILL,
              "gap-1.5",
              showMap ? "bg-muted text-white" : "bg-field-border text-white hover:bg-muted",
            )}
          >
            <Icon name="map" className="h-[15px] w-[15px]" />
            {showMap ? t.cards.hideMap : t.cards.map}
          </button>
        )}
        {card.ticket_url && (
          <a
            href={card.ticket_url}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(PILL, "gap-1.5 bg-secondary text-secondary-foreground hover:bg-secondary/90")}
          >
            <Icon name="tickets" className="h-[15px] w-[15px]" />
            {t.cards.tickets}
          </a>
        )}
      </footer>
    </article>
  );
}
