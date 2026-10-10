import { describe, expect, it, vi } from "vitest";
import { apiFetch } from "./client";
import { streamChat, type ChatMessage } from "./chat";

vi.mock("./client", () => ({ apiFetch: vi.fn() }));

const frame = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

describe("streamChat and the search context", () => {
  it("sends the latest search back and hands the new one over", async () => {
    vi.mocked(apiFetch).mockResolvedValue(
      new Response(frame("search.context", { searches: [{ city: "Torino" }] })),
    );
    const messages: ChatMessage[] = [
      { role: "user", content: "jazz in Bergamo" },
      { role: "assistant", content: "Two gigs.", context: [{ city: "Bergamo", genre: "jazz" }] },
      { role: "user", content: "thanks!" },
      { role: "assistant", content: "You're welcome." },
      { role: "user", content: "and next month?" },
    ];
    const onContext = vi.fn();

    await streamChat(messages, { handlers: { onContext } });

    const body = JSON.parse(vi.mocked(apiFetch).mock.calls[0]?.[1]?.body as string);
    expect(body.previous).toEqual([{ city: "Bergamo", genre: "jazz" }]);
    expect(body.messages[1]).toEqual({ role: "assistant", content: "Two gigs." });
    expect(onContext).toHaveBeenCalledWith([{ city: "Torino" }]);
  });
});
