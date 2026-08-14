import type { EventCard } from "@shared/protocol";
import { apiFetch } from "./client";
import { readProtocolStream, type ProtocolFrame } from "./sse";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  /** Cards that arrived with this answer (assistant turns only). */
  events?: EventCard[];
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
): Promise<void> {
  const { location, signal, handlers = {} } = options;

  const response = await apiFetch("/api/chat/stream", {
    method: "POST",
    signal,
    body: JSON.stringify({
      messages: messages.map(({ role, content }) => ({ role, content })),
      location: location ?? null,
      protocol: "v2",
    }),
  });

  for await (const frame of readProtocolStream(response)) {
    dispatch(frame, handlers);
  }
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
