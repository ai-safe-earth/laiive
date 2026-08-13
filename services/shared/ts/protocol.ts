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
  "batch.progress",
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
export interface FormExtracted {
  draft: EventDraft;
  missing: string[];
}

// event: batch.progress
export interface BatchProgress {
  index: number;
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
