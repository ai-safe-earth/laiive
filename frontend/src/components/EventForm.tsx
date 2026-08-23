import type { EventDraft } from "@shared/protocol";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { DraftFieldKey } from "@/i18n/translations";
import { useTranslation } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

/** Fields the graph write refuses without (laiive_shared.REQUIRED_DRAFT_FIELDS). */
const REQUIRED = ["artists", "start_at", "venue", "address", "city", "price_min"] as const;

/** `artists` is rendered on its own — it is a list, not a text field. */
const FIELDS: { key: DraftFieldKey & keyof EventDraft; type?: string }[] = [
  { key: "name" },
  { key: "start_at", type: "datetime-local" },
  { key: "venue" },
  { key: "address" },
  { key: "city" },
  { key: "price_min", type: "number" },
  { key: "price_max", type: "number" },
  { key: "price_currency" },
  { key: "genre" },
  { key: "ticket_url" },
  { key: "description" },
];

/** Pro fields: pill, warm-neutral, cyan focus. Never fuchsia below the header. */
const FIELD =
  "border-pro-border bg-control focus-visible:ring-pro-accent [color-scheme:dark]";

/** `datetime-local` wants "YYYY-MM-DDTHH:mm" and rejects anything longer. */
function toInputDateTime(value: string | null | undefined): string {
  if (!value) return "";
  return value.slice(0, 16);
}

function displayValue(draft: EventDraft, key: keyof EventDraft): string {
  const value = draft[key];
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join(", ");
  if (key === "start_at") return toInputDateTime(String(value));
  return String(value);
}

/** One row per artist, never fewer than one, so the list is always editable. */
function artistRows(draft: EventDraft): string[] {
  const artists = draft.artists ?? [];
  return artists.length > 0 ? [...artists] : [""];
}

/** Sentinel: `null` is a legitimate result (an empty field), so it cannot mean "bad". */
export const INVALID_URL = Symbol("invalid-url");

/**
 * A ticket link is typed the way it is spoken — "dice.fm/event/xyz" — and
 * stored verbatim it becomes a relative href, so the card's tickets pill would
 * send a reader to laiive.com/dice.fm/… A missing scheme is the common case,
 * not an error; anything that is still not a URL with one is.
 */
export function normalizeTicketUrl(raw: string | null | undefined): string | null | typeof INVALID_URL {
  const value = (raw ?? "").trim();
  if (!value) return null;
  // Any scheme at all, not just one with "//": `mailto:box@venue.it` prefixed
  // with https parses as a URL whose userinfo is "mailto:box", which passes
  // every check below and is not a ticket page.
  const hasScheme = /^[a-z][a-z0-9+.-]*:/i.test(value);
  try {
    const url = new URL(hasScheme ? value : `https://${value}`);
    if (!/^https?:$/.test(url.protocol)) return INVALID_URL;
    // A hostname with no dot is a typo or an intranet name; credentials in a
    // link a stranger will click are never what a promoter meant to paste.
    if (!url.hostname.includes(".") || url.username || url.password) return INVALID_URL;
    return url.toString();
  } catch {
    return INVALID_URL;
  }
}

/** Mono label; amber marks a field that still needs you, red one that is empty. */
function FieldLabel({ children, required, missing }: {
  children: React.ReactNode;
  required?: boolean;
  missing?: boolean;
}) {
  return (
    <span
      className={cn(
        "font-mono text-[11px] leading-none",
        missing ? "text-destructive" : "text-muted-foreground",
      )}
    >
      {children}
      {required && <span className={cn("ml-1", missing ? "text-destructive" : "text-secondary")}>*</span>}
    </span>
  );
}

/**
 * The last step of every submission path: whatever voice, a flyer, a document
 * or plain typing produced, it lands here for the human to complete and
 * approve. Saving is the only thing that writes to the graph.
 *
 * The one place in the app allowed a visible frame (brand-rules.md, "Promoter").
 */
export function EventForm({
  draft,
  missing,
  onSave,
  saving,
}: {
  draft: EventDraft;
  missing: string[];
  onSave: (draft: EventDraft) => void;
  saving: boolean;
}) {
  const { t } = useTranslation();
  const [values, setValues] = useState<EventDraft>(draft);
  // Held separately from `values.artists` so a half-typed row survives: the
  // draft's list is the saved shape, this is what the user is editing.
  const [artists, setArtists] = useState<string[]>(() => artistRows(draft));
  const [showTicketNote, setShowTicketNote] = useState(false);
  const [ticketError, setTicketError] = useState<string | null>(null);

  // Each turn re-extracts over the whole conversation, so a later message can
  // fill a field the user has not touched — take the server's draft as truth.
  useEffect(() => {
    setValues(draft);
    setArtists(artistRows(draft));
  }, [draft]);

  const filledArtists = artists.map((name) => name.trim()).filter(Boolean);

  const stillMissing = REQUIRED.filter((key) => {
    if (key === "artists") return filledArtists.length === 0;
    const value = values[key];
    return value === null || value === undefined || value === "";
  });

  const update = (key: keyof EventDraft, raw: string) => {
    setValues((current) => ({
      ...current,
      [key]:
        key === "price_min" || key === "price_max"
          ? raw === "" ? null : Number(raw)
          : raw === "" ? null : raw,
    }));
  };

  const setArtist = (index: number, name: string) =>
    setArtists((current) => current.map((value, i) => (i === index ? name : value)));

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        const ticket = normalizeTicketUrl(values.ticket_url);
        if (ticket === INVALID_URL) {
          setTicketError(t.form.ticketInvalid);
          return;
        }
        setTicketError(null);
        onSave({ ...values, ticket_url: ticket, artists: filledArtists });
      }}
      className="rounded-[20px] border-[1.5px] border-foreground/[0.32] bg-card px-6 py-[22px]"
    >
      <div className="flex items-center gap-[11px] pb-2">
        <span className="h-5 w-[5px] flex-none rounded-full bg-pro-accent" />
        <h3 className="font-bebas text-[23px] leading-none tracking-[0.05em] text-card-foreground">
          {t.form.title}
        </h3>
        {stillMissing.length > 0 && (
          <span className="ml-auto rounded-full border border-secondary/40 bg-secondary/10 px-2.5 py-[7px] font-mono text-[9.5px] uppercase leading-none tracking-[0.06em] text-secondary">
            {t.form.stillNeeded(stillMissing.length)}
          </span>
        )}
      </div>
      <div className="mb-[18px] h-px bg-hairline/[0.08]" />

      {/* Artists were a comma-separated text field, which could not be typed
          into: every keystroke split on "," and trimmed, so a space was eaten
          the moment it was typed and a comma vanished with it. One row per
          artist, and the list grows on demand. */}
      <div className="flex flex-col gap-[7px]">
        <FieldLabel required missing={stillMissing.includes("artists")}>
          {t.form.labels.artists}
        </FieldLabel>
        <div className="flex flex-col gap-2">
          {artists.map((name, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                value={name}
                onChange={(event) => setArtist(index, event.target.value)}
                placeholder={t.form.artistPlaceholder}
                className={cn(
                  FIELD,
                  stillMissing.includes("artists") &&
                    "border-destructive/60 focus-visible:ring-destructive",
                )}
              />
              {artists.length > 1 && (
                <button
                  type="button"
                  onClick={() => setArtists((current) => current.filter((_, i) => i !== index))}
                  aria-label={t.form.removeArtist}
                  className="flex h-11 w-11 flex-none items-center justify-center rounded-full text-pro-dim transition-colors hover:text-destructive"
                >
                  <Icon name="close" className="h-[18px] w-[18px]" />
                </button>
              )}
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setArtists((current) => [...current, ""])}
          className="self-start rounded-full py-2 font-mono text-[11px] text-pro-accent transition-opacity hover:opacity-80"
        >
          {t.form.addArtist}
        </button>
      </div>

      <div className="grid gap-x-5 gap-y-3.5 pt-3.5 sm:grid-cols-2">
        {FIELDS.map(({ key, type }) => {
          const isMissing = stillMissing.includes(key as (typeof REQUIRED)[number]);
          const wasMissing = missing.includes(key);
          const required = (REQUIRED as readonly string[]).includes(key);
          const isTicket = key === "ticket_url";
          return (
            // A div and an explicit htmlFor rather than a wrapping label: the
            // ticket field carries a button, and a button inside a label
            // focuses the input on every press.
            <div key={key} className="flex flex-col gap-[7px]">
              <span className="flex items-center gap-1.5">
                <label htmlFor={`field-${key}`}>
                  <FieldLabel required={required} missing={isMissing}>
                    {t.form.labels[key]}
                  </FieldLabel>
                </label>
                {isTicket && (
                  <button
                    type="button"
                    onClick={() => setShowTicketNote(!showTicketNote)}
                    aria-expanded={showTicketNote}
                    aria-label={t.form.ticketNoteAria}
                    // A title attribute is a hover, and a phone has no hover.
                    // Same 44px-under-a-small-mark trick the cards use.
                    className="relative flex-none text-pro-dim transition-colors after:absolute after:-inset-3 after:content-[''] hover:text-pro-accent"
                  >
                    <Icon name="error" className="h-[13px] w-[13px]" />
                  </button>
                )}
              </span>
              <Input
                id={`field-${key}`}
                type={type ?? "text"}
                value={displayValue(values, key)}
                onChange={(event) => update(key, event.target.value)}
                placeholder={wasMissing ? t.form.missingPlaceholder : ""}
                className={cn(
                  FIELD,
                  isMissing && "border-destructive/60 focus-visible:ring-destructive",
                )}
              />
              {isTicket && showTicketNote && (
                <p className="text-[12px] leading-[1.45] text-pro-muted">
                  {t.form.ticketNote}
                </p>
              )}
              {isTicket && ticketError && (
                <p className="text-[12px] leading-[1.45] text-destructive">{ticketError}</p>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-3.5 pt-5">
        <Button
          type="submit"
          variant="cream"
          disabled={saving || stillMissing.length > 0}
        >
          {saving ? t.form.publishing : t.form.publish}
        </Button>
        {stillMissing.length > 0 && (
          <span className="text-[12.5px] leading-[1.4] text-muted-foreground">
            {t.form.fillHint(stillMissing.map((key) => t.form.labels[key]).join(", "))}
          </span>
        )}
      </div>
    </form>
  );
}
