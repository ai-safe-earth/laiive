/**
 * TS mirror of laiive_shared/protocol.py + cards.py.
 * Field names are the JSON wire names (snake_case) — do not camelCase them.
 * tests/test_ts_contract.py diffs these interfaces against the pydantic
 * models; a field added on one side only fails CI.
 */

export const SSE_EVENTS = [
  "message.delta",
  "events.result",
  "form.extracted",
  "walk.state",
  "status",
  "error",
  "done",
] as const;

export type SSEEventName = (typeof SSE_EVENTS)[number];

export interface EventCard {
  uid: string;
  name: string;
  artists: string[];
  venue?: string | null;
  // The venue's graph identity and address — what the ownership screens
  // reference. Null on rows read by paths that do not select them.
  venue_uid?: string | null;
  venue_address?: string | null;
  venue_type?: string | null;
  city?: string | null;
  start_at?: string | null;
  // IANA zone of the venue, so the card prints the time at the door rather
  // than on the reader's clock. Empty or null is a row written before the
  // writer resolved zones, whose start_at is UTC by default.
  timezone?: string | null;
  price_min?: number | null;
  price_max?: number | null;
  price_currency?: string | null;
  description?: string | null;
  ticket_url?: string | null;
  lat?: number | null;
  lng?: number | null;
  source: string;
  // The page a discovered event was read off, and its host. Empty or null on a
  // promoter submission and on rows written before the writer carried it.
  source_url?: string | null;
  source_domain?: string | null;
  distance_km?: number | null;
  // false when the listing gave a date and no time: start_at's 00:00 is a
  // default, so the card must show the day without an hour.
  start_time_known?: boolean | null;
  // 'venue' | 'city_centroid' | null -- how precisely lat/lng locates the
  // event. A centroid means "somewhere in this city", so the map must not
  // draw it as a street address.
  geocode_precision?: string | null;
  // true once an organization's verified claim stamped the graph node — the
  // card treats it as vouched, like a promoter's own submission.
  claimed?: boolean;
}

// GET /api/venues — one venue in a lookup answer, enough to pick it and
// prefill the event form.
export interface VenueHit {
  uid: string;
  name: string;
  venue_type?: string | null;
  address?: string | null;
  city?: string | null;
}

export interface VenueLookupResult {
  venues: VenueHit[];
}

// GET /api/artists
export interface ArtistHit {
  uid: string;
  name: string;
  genres: string[];
}

export interface ArtistLookupResult {
  artists: ArtistHit[];
}

export interface EventDraft {
  name?: string | null;
  artists: string[];
  start_at?: string | null;
  /** The date as the source worded it, kept so it can be checked against start_at. */
  start_at_claim?: string | null;
  venue?: string | null;
  venue_type?: string | null;
  address?: string | null;
  city?: string | null;
  price_min?: number | null;
  price_max?: number | null;
  price_currency?: string | null;
  description?: string | null;
  genre?: string | null;
  ticket_url?: string | null;
}

/** A value the correction layer changed, and what it was before. */
export interface Correction {
  field: string;
  before: string;
  after: string;
  why: string;
}

/** Something the correction layer could not settle on its own. */
export interface Doubt {
  field: string;
  question: string;
}

// event: message.delta
export interface MessageDelta {
  text: string;
}

// event: events.result
export interface EventsResult {
  events: EventCard[];
}

// event: form.extracted
// One frame per recognized event, in source order: a turn that reads a
// spreadsheet or a festival line-up emits several, and the client shows them
// one at a time. A single event is index 0 of 1.
export interface FormExtracted {
  draft: EventDraft;
  missing: string[];
  /** Already applied to `draft`; shown so the promoter can overrule them. */
  corrections: Correction[];
  /** Questions only the promoter can settle; the reply asks them. */
  doubts: Doubt[];
  index: number;
  total: number;
}

// event: walk.state
// A turn that recognized several events starts a walk: this frame carries the
// whole set, the client persists it and echoes it back with each message, and
// form.extracted shows only the event under the cursor. A single event never
// enters a walk.
export interface WalkState {
  drafts: EventDraft[];
  missing: string[][];
  cursor: number;
  total: number;
}

// event: status
export interface Status {
  state: string;
}

// event: error
export interface Error {
  code: string;
  message: string;
}

// event: done
export interface Done {
  request_id: string;
}
