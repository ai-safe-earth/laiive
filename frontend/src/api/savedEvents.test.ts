import { describe, expect, it, vi } from "vitest";
import { fetchEventsByUid, LOOKUP_CHUNK } from "./savedEvents";

const api = vi.hoisted(() => ({ fetch: vi.fn() }));
vi.mock("@/api/client", () => ({ apiFetch: api.fetch, ApiError: class extends Error {} }));
// The list half of the module never runs here; the client is imported at
// module scope, so it still has to resolve.
vi.mock("@/auth/supabase", () => ({ supabase: {} }));

function respondWith(uids: string[]) {
  return {
    json: () => Promise.resolve({ events: uids.map((uid) => ({ uid })) }),
  };
}

describe("fetching the bodies for a saved list", () => {
  it("asks in chunks the retriever will accept, and keeps the order", async () => {
    const uids = Array.from({ length: LOOKUP_CHUNK * 2 + 20 }, (_, i) => `e${i}`);
    api.fetch.mockImplementation((path: string) => {
      const asked = new URL(path, "http://x").searchParams.get("uids")!.split(",");
      return Promise.resolve(respondWith(asked));
    });

    const cards = await fetchEventsByUid(uids);

    expect(api.fetch).toHaveBeenCalledTimes(3);
    expect(cards.map((c) => c.uid)).toEqual(uids);
  });

  it("makes no request at all for an empty list", async () => {
    api.fetch.mockClear();
    expect(await fetchEventsByUid([])).toEqual([]);
    expect(api.fetch).not.toHaveBeenCalled();
  });

  it("escapes a uid rather than letting it end the query", async () => {
    api.fetch.mockClear();
    api.fetch.mockResolvedValue(respondWith([]));
    await fetchEventsByUid(["a,b"]);
    expect(api.fetch).toHaveBeenCalledWith("/api/events?uids=a%2Cb");
  });
});
