import type { EventDraft, FormExtracted, WalkState } from "@shared/protocol";
import { apiFetch } from "./client";
import { readProtocolStream } from "./sse";
import type { ChatMessage } from "./chat";

export interface SubmissionHandlers {
  onStatus?: (state: string) => void;
  /**
   * The whole frame, not its fields spread out: it already carries four things
   * and now carries corrections and doubts too, and a six-argument callback is
   * a place for two of them to end up swapped.
   */
  onForm?: (form: FormExtracted) => void;
  onWalk?: (walk: WalkState) => void;
  onDelta?: (text: string) => void;
  onError?: (message: string) => void;
}

/** The client-carried walk state, echoed back with each message. */
export interface WalkEcho {
  drafts: EventDraft[];
  cursor: number;
}

/**
 * One submission-chat turn against the pusher.
 *
 * The pusher is stateless: the whole conversation goes up every turn and
 * extraction runs over all of it, which is why text pulled out of a flyer or a
 * recording only has to be appended to `messages` to be merged into the draft.
 *
 * A turn that recognized several events starts a walk — the server hands the
 * whole draft set back in walk.state, and we echo it (with the cursor) via
 * `walk` on every following turn so it can refine just the current event.
 */
export async function streamSubmission(
  messages: ChatMessage[],
  options: {
    signal?: AbortSignal;
    handlers?: SubmissionHandlers;
    walk?: WalkEcho | null;
  } = {},
): Promise<void> {
  const { signal, handlers = {}, walk } = options;

  const response = await apiFetch("/api/push/chat/stream", {
    method: "POST",
    signal,
    body: JSON.stringify({
      messages: messages.map(({ role, content }) => ({ role, content })),
      ...(walk ? { walk } : {}),
    }),
  });

  for await (const frame of readProtocolStream(response)) {
    switch (frame.event) {
      case "status":
        handlers.onStatus?.(frame.data.state);
        break;
      case "form.extracted":
        handlers.onForm?.(frame.data);
        break;
      case "walk.state":
        handlers.onWalk?.(frame.data);
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
 *
 * `venueUid` is the graph venue the form picked from the lookup. It travels
 * beside the draft, never on it: drafts round-trip through an LLM mid-walk,
 * and the writer must be able to trust that a uid was a human's pick.
 *
 * Posted to /api/publish rather than straight at the pusher: the gateway
 * forwards the same body and then records what the write created against the
 * promoter's organization, bootstrapping one if they have none. Publishing
 * without that hop leaves a promoter not owning their own event, and nothing
 * afterwards knows it was theirs.
 */
export async function saveEvent(
  draft: EventDraft,
  venueUid?: string | null,
): Promise<SavedEvent> {
  const response = await apiFetch("/api/publish", {
    method: "POST",
    body: JSON.stringify({ draft, ...(venueUid ? { venue_uid: venueUid } : {}) }),
  });
  return (await response.json()) as SavedEvent;
}
