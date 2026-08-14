import type {
  Done,
  Error as ProtocolError,
  EventsResult,
  FormExtracted,
  MessageDelta,
  SSEEventName,
  Status,
  WalkState,
} from "@shared/protocol";

/**
 * Parser for the v2 named-event protocol (services/shared/protocol.py).
 *
 * Frames look like:
 *   event: message.delta\ndata: {"text":"…"}\n\n
 *
 * The old client only understood OpenAI-shaped anonymous `data:` frames, which
 * is why it had to scrape events back out of markdown. Here the event name is
 * the discriminator and cards arrive as data.
 */
export type ProtocolFrame =
  | { event: "message.delta"; data: MessageDelta }
  | { event: "events.result"; data: EventsResult }
  | { event: "form.extracted"; data: FormExtracted }
  | { event: "walk.state"; data: WalkState }
  | { event: "status"; data: Status }
  | { event: "error"; data: ProtocolError }
  | { event: "done"; data: Done };

const KNOWN: ReadonlySet<string> = new Set<SSEEventName>([
  "message.delta",
  "events.result",
  "form.extracted",
  "walk.state",
  "status",
  "error",
  "done",
]);

/** Split one raw SSE block into its event name and JSON payload. */
function parseBlock(block: string): ProtocolFrame | null {
  let name = "";
  const dataLines: string[] = [];

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }

  if (!KNOWN.has(name) || dataLines.length === 0) return null;

  try {
    return { event: name, data: JSON.parse(dataLines.join("\n")) } as ProtocolFrame;
  } catch {
    // A truncated frame (aborted stream) is not worth killing the turn over.
    return null;
  }
}

/**
 * Yields protocol frames as they arrive. Consumers get real incremental
 * delivery — the retriever streams composer tokens one frame at a time.
 */
export async function* readProtocolStream(
  response: Response,
): AsyncGenerator<ProtocolFrame> {
  if (!response.body) throw new Error("response has no body");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Frames are separated by a blank line; keep the tail for the next read.
      let split = buffer.indexOf("\n\n");
      while (split !== -1) {
        const block = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        const frame = parseBlock(block);
        if (frame) yield frame;
        split = buffer.indexOf("\n\n");
      }
    }

    const trailing = parseBlock(buffer);
    if (trailing) yield trailing;
  } finally {
    reader.releaseLock();
  }
}
