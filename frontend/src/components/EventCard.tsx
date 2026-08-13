import { useState } from "react";

export interface EventData {
  artist: string;
  tagline: string;
  venue: string;
  time: string;
  price: string;
  description?: string;
  ticketUrl?: string;
}

/**
 * Parse event blocks from markdown-formatted assistant messages.
 * Pattern: **Artist**\nTagline\nVenue | Time | Price\nDescription\n[tickets](url)
 */
export function parseEventContent(content: string) {
  const eventPattern =
    /\*\*(.+?)\*\*\n(.+?)\n(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)(?:\n(.+?))?(?:\n\[tickets\]\((.+?)\))?(?=\n\n\*\*|$)/gs;
  const events: EventData[] = [];
  const textParts: string[] = [];

  let lastIndex = 0;

  // Get text before first event (intro sentence)
  const firstEventMatch = content.match(/\*\*(.+?)\*\*\n/);
  if (firstEventMatch?.index !== undefined && firstEventMatch.index > 0) {
    textParts.push(content.slice(0, firstEventMatch.index));
    lastIndex = firstEventMatch.index;
  }

  let match;
  while ((match = eventPattern.exec(content)) !== null) {
    events.push({
      artist: match[1]?.trim(),
      tagline: match[2]?.trim(),
      venue: match[3]?.trim(),
      time: match[4]?.trim(),
      price: match[5]?.trim(),
      description: match[6]?.trim(),
      ticketUrl: match[7]?.trim(),
    });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length && events.length > 0) {
    const remaining = content.slice(lastIndex).trim();
    if (remaining) textParts.push(remaining);
  }

  if (events.length === 0) {
    textParts.push(content);
  }

  return { events, textParts, hasEvents: events.length > 0 };
}

export function EventCard({ event }: { event: EventData }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-border/50 rounded-lg p-3 sm:p-4 my-2 bg-card hover:border-primary/30 transition-colors">
      <div className="space-y-1">
        <h4 className="font-semibold text-foreground text-base">
          {event.artist}
        </h4>
        <div className="flex items-center gap-2">
          <p className="text-sm text-muted-foreground flex-1">
            {event.tagline}
          </p>
          {event.description && event.description !== event.tagline && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-muted-foreground/70 hover:text-primary transition-colors shrink-0"
            >
              {expanded ? "− less" : "+ more"}
            </button>
          )}
        </div>
        {expanded && event.description && event.description !== event.tagline && (
          <p className="text-sm text-muted-foreground pt-1">
            {event.description}
          </p>
        )}
        <div className="flex items-center gap-3 text-sm pt-1">
          <span className="text-muted-foreground">{event.venue}</span>
          <span className="text-muted-foreground">{event.time}</span>
          <span className="text-primary font-medium">{event.price}</span>
        </div>
        {event.ticketUrl && (
          <a
            href={event.ticketUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block text-sm text-primary hover:underline pt-1"
          >
            tickets →
          </a>
        )}
      </div>
    </div>
  );
}
