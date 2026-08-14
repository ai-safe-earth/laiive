import type { EventDraft } from "@shared/protocol";
import { apiFetch } from "./client";
import { readProtocolStream } from "./sse";
import type { ChatMessage } from "./chat";

export interface SubmissionHandlers {
  onStatus?: (state: string) => void;
  onForm?: (draft: EventDraft, missing: string[]) => void;
  onDelta?: (text: string) => void;
  onError?: (message: string) => void;
}

/**
 * One submission-chat turn against the pusher.
 *
 * The pusher is stateless: the whole conversation goes up every turn and
 * extraction runs over all of it, which is why text pulled out of a flyer or a
 * recording only has to be appended to `messages` to be merged into the draft.
 */
export async function streamSubmission(
  messages: ChatMessage[],
  options: { signal?: AbortSignal; handlers?: SubmissionHandlers } = {},
): Promise<void> {
  const { signal, handlers = {} } = options;

  const response = await apiFetch("/api/push/chat/stream", {
    method: "POST",
    signal,
    body: JSON.stringify({
      messages: messages.map(({ role, content }) => ({ role, content })),
    }),
  });

  for await (const frame of readProtocolStream(response)) {
    switch (frame.event) {
      case "status":
        handlers.onStatus?.(frame.data.state);
        break;
      case "form.extracted":
        handlers.onForm?.(frame.data.draft, frame.data.missing);
        break;
      case "message.delta":
        handlers.onDelta?.(frame.data.text);
        break;
      case "error":
        handlers.onError?.(frame.data.message);
        break;
      default:
        break;
    }
  }
}

export interface SavedEvent {
  success: boolean;
  event_id: string;
  event_name: string;
  artist?: string | null;
  venue?: string | null;
  city?: string | null;
  warnings?: string[];
}

/**
 * Publish the completed draft. The service does dedup, geocoding and the
 * embedding calculations on the way into the graph — the client never computes
 * an embedding or writes Cypher.
 */
export async function saveEvent(draft: EventDraft): Promise<SavedEvent> {
  const response = await apiFetch("/api/push/validate-event", {
    method: "POST",
    body: JSON.stringify({ draft }),
  });
  return (await response.json()) as SavedEvent;
}
