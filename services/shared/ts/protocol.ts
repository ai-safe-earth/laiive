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
  venue_type?: string | null;
  city?: string | null;
  start_at?: string | null;
  price_min?: number | null;
  price_max?: number | null;
  price_currency?: string | null;
  description?: string | null;
  ticket_url?: string | null;
  lat?: number | null;
  lng?: number | null;
  source: string;
  distance_km?: number | null;
}

export interface EventDraft {
  name?: string | null;
  artists: string[];
  start_at?: string | null;
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
