/**
 * Shared API types — these mirror the backend Pydantic models
 * in services/retriever/agent/api.py and services/pusher/agent/api.py.
 *
 * Keep in sync when backend models change.
 */

// ─── Chat (Retriever) ───────────────────────────────────────────

export interface UserLocation {
  latitude: number;
  longitude: number;
  city?: string;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

/** POST /chat/stream (SSE) */
export interface ChatStreamRequest {
  messages: ChatMessage[];
  location?: UserLocation | null;
  language?: string;
}

/** POST /chat (JSON) */
export interface ChatJSONRequest {
  message: string;
  conversation_history?: ChatMessage[];
}

export interface ChatJSONResponse {
  request_id: string;
  response: string;
  cypher?: string | null;
  results?: EventResult[] | null;
  used_query: boolean;
  needs_more_info: boolean;
}

// ─── Events ─────────────────────────────────────────────────────

/** Event as returned by the retriever's formatter (Neo4j → frontend) */
export interface EventResult {
  name: string;
  artist?: string;
  venue?: string;
  city?: string;
  start_at?: string;
  price_amount?: number;
  price_currency?: string;
  description?: string;
  ticket_url?: string;
  source?: "user_submission" | "verified" | "internet";
}

/** Event details for the promoter creation/confirmation flow */
export interface EventDetails {
  name: string;
  artist?: string | null;
  description?: string | null;
  event_date: string;
  venue: string;
  city: string;
  price?: number | null;
  ticket_url?: string | null;
}

// ─── Pusher ─────────────────────────────────────────────────────

/** POST /chat on the pusher service */
export interface PusherChatRequest {
  session_id?: string;
  message: string;
}

export interface PusherChatResponse {
  session_id: string;
  reply: string;
  fields: Record<string, string | null>;
  confirmed: boolean;
  event?: EventResult | null;
}

// ─── Entities (Supabase) ────────────────────────────────────────

export type EntityType = "venue" | "band" | "festival";

export interface VenueEntity {
  id: string;
  name: string;
  description?: string | null;
  capacity?: number | null;
  atmosphere?: string | null;
  address?: string | null;
  city?: string | null;
  country?: string | null;
  contact?: string | null;
  phone?: string | null;
  link?: string | null;
  promoter_id: string;
  created_by?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface BandEntity {
  id: string;
  name: string;
  description?: string | null;
  members?: string | null;
  year_of_formation?: number | null;
  genre?: string | null;
  influences?: string | null;
  promoter_id: string;
  created_by?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface FestivalEntity {
  id: string;
  name: string;
  description?: string | null;
  first_edition?: number | null;
  genres?: string | null;
  past_artists?: string | null;
  address?: string | null;
  city?: string | null;
  country?: string | null;
  promoter_id: string;
  created_by?: string | null;
  created_at?: string;
  updated_at?: string;
}

// ─── Profiles ───────────────────────────────────────────────────

export interface UserProfile {
  id: string;
  display_name?: string | null;
}

export interface PromoterProfile {
  id: string;
  user_id: string;
  first_name: string;
  last_name: string;
  city: string;
  country: string;
  industry_role: string;
}

export interface QueryUsage {
  user_id: string;
  week_start: string;
  query_count: number;
}
