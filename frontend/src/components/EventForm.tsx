import type { Correction, EventDraft, VenueHit } from "@shared/protocol";
import { useEffect, useRef, useState } from "react";
import { foldName, useVenueLookup } from "@/api/lookup";
import { Icon } from "@/components/Icon";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { DraftFieldKey } from "@/i18n/translations";
import { useTranslation } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

/** Fields the graph write refuses without (laiive_shared.REQUIRED_DRAFT_FIELDS). */
const REQUIRED = ["artists", "start_at", "venue", "address", "city", "price_min"] as const;

/**
 * `artists` is rendered on its own (a list, not a text field), and `venue` +
 * `address` leave the generic grid too: the venue is a combobox over the
 * graph, and the address input only exists while no picked venue answers it.
 */
const FIELDS_LEAD: { key: DraftFieldKey & keyof EventDraft; type?: string }[] = [
  { key: "name" },
  { key: "start_at", type: "datetime-local" },
];
const FIELDS_REST: { key: DraftFieldKey & keyof EventDraft; type?: string }[] = [
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
        "font-mono text-xs leading-none",
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
  corrections = [],
  doubted = [],
  onSave,
  saving,
}: {
  draft: EventDraft;
  missing: string[];
  /**
   * Values the correction layer already changed on this draft. Listed above the
   * fields rather than applied invisibly: a correction nobody is told about is
   * an edit made on the promoter's behalf, and this form is the step where they
   * get to disagree with it.
   */
  corrections?: Correction[];
  /** Fields carrying a question the chat asked. Marked, never blocked. */
  doubted?: string[];
  /** The second argument is the picked graph venue's uid, when there is one. */
  onSave: (draft: EventDraft, venueUid: string | null) => void;
  saving: boolean;
}) {
  const { t } = useTranslation();
  const [values, setValues] = useState<EventDraft>(draft);
  // Held separately from `values.artists` so a half-typed row survives: the
  // draft's list is the saved shape, this is what the user is editing.
  const [artists, setArtists] = useState<string[]>(() => artistRows(draft));
  // The graph venue the promoter picked from the lookup. Client-side state
  // only — the uid goes up beside the draft at publish, never inside it.
  const [pick, setPick] = useState<VenueHit | null>(null);
  const [venueOpen, setVenueOpen] = useState(false);
  const [activeHit, setActiveHit] = useState(0);
  const [showTicketNote, setShowTicketNote] = useState(false);
  const [ticketError, setTicketError] = useState<string | null>(null);
  // Read by the draft-refresh effect without retriggering it, and by unpick.
  const pickRef = useRef<VenueHit | null>(null);
  pickRef.current = pick;
  // What the promoter had typed into the address before a pick answered it —
  // dropping the pick must give their words back, not an empty field.
  const stashedAddress = useRef<string | null>(null);

  // Each turn re-extracts over the whole conversation, so a later message can
  // fill a field the user has not touched — take the server's draft as truth.
  // Except the venue while a pick stands: the server never saw the pick and
  // respells freely, so the settled identity survives any refresh that still
  // names it. Containment, not equality — the pick was found BY a typed
  // fragment ("razz" found "Razzmatazz") the server keeps re-emitting.
  useEffect(() => {
    const current = pickRef.current;
    const extracted = foldName(draft.venue ?? "");
    const pickedName = current ? foldName(current.name) : "";
    const kept =
      current !== null &&
      extracted !== "" &&
      (pickedName.includes(extracted) || extracted.includes(pickedName))
        ? current
        : null;
    setPick(kept);
    setValues(
      kept
        ? { ...draft, venue: kept.name, address: kept.address ?? draft.address }
        : draft,
    );
    setArtists(artistRows(draft));
  }, [draft]);

  const lookup = useVenueLookup(
    values.venue ?? "",
    values.city,
    venueOpen && pick === null,
  );
  const hits = lookup.data?.venues ?? [];
  const suggestionsOpen = venueOpen && !pick && hits.length > 0;

  useEffect(() => setActiveHit(0), [hits]);

  const choose = (hit: VenueHit) => {
    stashedAddress.current = values.address ?? null;
    setPick(hit);
    setVenueOpen(false);
    setValues((current) => ({
      ...current,
      venue: hit.name,
      city: current.city || hit.city || null,
      venue_type: current.venue_type ?? hit.venue_type ?? null,
      // The on-file address rides INTO the draft rather than being nulled:
      // the walk's own missing_required then sees it (so the chat stops
      // asking for an address the graph already has), and the writer's
      // coalesce makes the round-trip a no-op on the node.
      address: hit.address ?? current.address,
    }));
  };

  const unpick = () => {
    const current = pickRef.current;
    if (!current) return;
    setPick(null);
    if (current.address != null) {
      // The pick's on-file address is not the promoter's to submit unpicked.
      setValues((values_) => ({ ...values_, address: stashedAddress.current }));
    }
  };

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

  const renderField = ({
    key,
    type,
  }: {
    key: DraftFieldKey & keyof EventDraft;
    type?: string;
  }) => {
          const isMissing = stillMissing.includes(key as (typeof REQUIRED)[number]);
          const wasMissing = missing.includes(key);
          const isDoubted = doubted.includes(key);
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
                {isDoubted && (
                  // The question itself was asked in the chat, in their own
                  // language; this only says which field it was about.
                  <span className="font-mono text-2xs uppercase tracking-[0.11em] text-status-waiting">
                    {t.form.checkThis}
                  </span>
                )}
                {isTicket && (
                  <button
                    type="button"
                    onClick={() => setShowTicketNote(!showTicketNote)}
                    aria-expanded={showTicketNote}
                    aria-label={t.form.ticketNoteAria}
                    // A title attribute is a hover, and a phone has no hover.
                    // Same 44px-under-a-small-mark trick the cards use.
                    className="relative flex-none text-pro-dim transition-colors after:absolute after:-inset-4 after:content-[''] hover:text-pro-accent"
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
                  !isMissing && isDoubted && "border-status-waiting/60",
                )}
              />
              {isTicket && showTicketNote && (
                <p className="text-sm leading-[1.45] text-pro-muted">
                  {t.form.ticketNote}
                </p>
              )}
              {isTicket && ticketError && (
                <p className="text-sm leading-[1.45] text-destructive">{ticketError}</p>
              )}
            </div>
          );
  };

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
        onSave(
          { ...values, ticket_url: ticket, artists: filledArtists },
          pick?.uid ?? null,
        );
      }}
      className="rounded-[20px] border-[1.5px] border-foreground/[0.32] bg-card px-6 py-[22px]"
    >
      <div className="flex items-center gap-[11px] pb-2">
        <span className="h-5 w-[5px] flex-none rounded-full bg-pro-accent" />
        <h3 className="font-bebas text-3xl leading-none tracking-[0.05em] text-card-foreground">
          {t.form.title}
        </h3>
        {stillMissing.length > 0 && (
          <span className="ml-auto rounded-full border border-secondary/40 bg-secondary/10 px-2.5 py-[7px] font-mono text-2xs uppercase leading-none tracking-[0.06em] text-secondary">
            {t.form.stillNeeded(stillMissing.length)}
          </span>
        )}
      </div>
      <div className="mb-[18px] h-px bg-hairline/[0.08]" />

      {/* What was changed on the way here, and what it was before. Shown above
          the fields rather than beside them: the promoter is about to read the
          whole form anyway, and a per-field marker would say something was
          altered without saying what it used to be — which is the one fact
          needed to disagree with it. */}
      {corrections.length > 0 && (
        <div className="mb-[18px] rounded-[14px] border border-hairline/[0.08] bg-muted/[0.04] px-4 py-3">
          <p className="font-mono text-2xs uppercase tracking-[0.11em] text-muted-foreground">
            {t.form.correctedTitle}
          </p>
          <ul className="mt-2 flex flex-col gap-1">
            {corrections.map((correction) => (
              <li key={correction.field} className="text-sm text-card-foreground">
                <span className="text-muted-foreground">
                  {t.form.labels[correction.field as keyof typeof t.form.labels] ??
                    correction.field}
                  {": "}
                </span>
                <span className="line-through opacity-60">{correction.before}</span>
                {" → "}
                <span>{correction.after}</span>
                <span className="text-muted-foreground"> ({correction.why})</span>
              </li>
            ))}
          </ul>
        </div>
      )}

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
          className="min-h-11 self-start rounded-full font-mono text-xs text-pro-accent transition-opacity hover:opacity-80"
        >
          {t.form.addArtist}
        </button>
      </div>

      <div className="grid gap-x-5 gap-y-3.5 pt-3.5 sm:grid-cols-2">
        {FIELDS_LEAD.map(renderField)}

        {/* Venue: a combobox over the graph. Picking an existing venue reuses
            its identity (and its address below); typing past a pick clears it,
            because the text no longer names what was picked. */}
        <div className="relative flex flex-col gap-[7px]">
          <label htmlFor="field-venue">
            <FieldLabel required missing={stillMissing.includes("venue")}>
              {t.form.labels.venue}
            </FieldLabel>
          </label>
          <Input
            id="field-venue"
            autoComplete="off"
            role="combobox"
            aria-expanded={suggestionsOpen}
            aria-controls="venue-suggestions"
            aria-activedescendant={
              suggestionsOpen && hits[activeHit]
                ? `venue-option-${hits[activeHit]!.uid}`
                : undefined
            }
            value={values.venue ?? ""}
            onChange={(event) => {
              update("venue", event.target.value);
              unpick();
              setVenueOpen(true);
            }}
            onFocus={() => setVenueOpen(true)}
            onBlur={() => setVenueOpen(false)}
            onKeyDown={(event) => {
              if (!suggestionsOpen) return;
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setActiveHit((i) => Math.min(i + 1, hits.length - 1));
              } else if (event.key === "ArrowUp") {
                event.preventDefault();
                setActiveHit((i) => Math.max(i - 1, 0));
              } else if (event.key === "Enter") {
                // Picks instead of submitting the form — only while the list
                // is open, so Enter on a settled field still publishes.
                event.preventDefault();
                choose(hits[activeHit] ?? hits[0]!);
              } else if (event.key === "Escape") {
                setVenueOpen(false);
              }
            }}
            placeholder={missing.includes("venue") ? t.form.missingPlaceholder : ""}
            className={cn(
              FIELD,
              stillMissing.includes("venue") &&
                "border-destructive/60 focus-visible:ring-destructive",
            )}
          />
          {suggestionsOpen && (
            <ul
              id="venue-suggestions"
              role="listbox"
              aria-label={t.form.venueSuggestionsAria}
              className="absolute top-full z-10 mt-1 w-full overflow-hidden rounded-[14px] border border-pro-border bg-pro-elevated"
            >
              {hits.map((hit, index) => (
                <li key={hit.uid}>
                  <button
                    type="button"
                    role="option"
                    id={`venue-option-${hit.uid}`}
                    aria-selected={index === activeHit}
                    // Keep focus in the input, so blur cannot close the list
                    // before this click lands.
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => choose(hit)}
                    className={cn(
                      "min-h-11 w-full px-4 py-2.5 text-left transition-colors hover:bg-pro-card",
                      index === activeHit && "bg-pro-card",
                    )}
                  >
                    <span className="text-md text-pro-fg">{hit.name}</span>
                    {hit.city && (
                      <span className="font-mono text-2xs text-pro-dim"> · {hit.city}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {pick?.address ? (
          <div className="flex flex-col gap-[7px]">
            <FieldLabel>{t.form.labels.address}</FieldLabel>
            {/* The graph already knows this venue's street — show it, never
                re-ask. Correcting a stated address is an owner's edit, not a
                submission field. */}
            <p className="flex min-h-11 items-center rounded-full border border-pro-border bg-pro-bg px-4 font-mono text-xs leading-[1.4] text-pro-muted">
              {pick.address} · {t.form.addressOnFile}
            </p>
          </div>
        ) : (
          renderField({ key: "address" })
        )}

        {FIELDS_REST.map(renderField)}
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
          <span className="text-sm leading-[1.4] text-muted-foreground">
            {t.form.fillHint(stillMissing.map((key) => t.form.labels[key]).join(", "))}
          </span>
        )}
      </div>
    </form>
  );
}
