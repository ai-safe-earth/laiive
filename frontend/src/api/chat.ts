import type { EventCard } from "@shared/protocol";
import { apiFetch } from "./client";
import { readProtocolStream, type ProtocolFrame } from "./sse";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  /** Cards that arrived with this answer (assistant turns only). */
  events?: EventCard[];
  /** The gateway's x-request-id for the turn that produced this answer —
   * the join key for feedback (assistant turns only, set once done). */
  requestId?: string;
}

export interface UserLocation {
  latitude: number;
  longitude: number;
  city?: string;
}

export interface StreamHandlers {
  onStatus?: (state: string) => void;
  onEvents?: (events: EventCard[]) => void;
  onDelta?: (text: string) => void;
  onError?: (message: string) => void;
}

/** The reader's IANA zone, or null where Intl cannot name one. */
function browserTimezone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}

/**
 * One chat turn against the retriever, through the gateway.
 *
 * `events.result` always precedes the first prose delta, so the UI can render
 * cards before the composer finishes talking about them.
 */
export async function streamChat(
  messages: ChatMessage[],
  options: {
    location?: UserLocation | null;
    signal?: AbortSignal;
    handlers?: StreamHandlers;
  } = {},
): Promise<string | null> {
  const { location, signal, handlers = {} } = options;

  const response = await apiFetch("/api/chat/stream", {
    method: "POST",
    signal,
    body: JSON.stringify({
      messages: messages.map(({ role, content }) => ({ role, content })),
      location: location ?? null,
      // "tonight" has to be resolved against the asker's clock, not the
      // server's. Sent every turn because it is free and a laptop crossing a
      // border between turns is exactly the case that would otherwise be wrong.
      timezone: browserTimezone(),
    }),
  });

  for await (const frame of readProtocolStream(response)) {
    dispatch(frame, handlers);
  }
  return response.headers.get("x-request-id");
}

/**
 * Thumbs-down on an assistant turn. The click fires immediately with no
 * reason — abandoning the reason box must not lose the signal — and a typed
 * reason arrives as a second post for the same request_id. Server-side, the
 * id joins the full conversation (conversation_logs) and the answer
 * (eval_records).
 */
export async function sendFeedback(requestId: string, reason?: string): Promise<void> {
  await apiFetch("/api/chat/feedback", {
    method: "POST",
    body: JSON.stringify({ request_id: requestId, reason: reason ?? null }),
  });
}

function dispatch(frame: ProtocolFrame, handlers: StreamHandlers): void {
  switch (frame.event) {
    case "status":
      handlers.onStatus?.(frame.data.state);
      break;
    case "events.result":
      handlers.onEvents?.(frame.data.events);
      break;
    case "message.delta":
      handlers.onDelta?.(frame.data.text);
      break;
    case "error":
      handlers.onError?.(frame.data.message);
      break;
    default:
      // form.extracted belongs to the pusher flow; done needs no handling —
      // the stream ending is the signal.
      break;
  }
}
