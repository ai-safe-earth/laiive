import { beforeEach, describe, expect, it, vi } from "vitest";
import { becomePromoter, PromoterRefreshError } from "./becomePromoter";
import { supabase } from "./supabase";

vi.mock("./supabase", () => ({
  supabase: {
    from: vi.fn(),
    auth: { refreshSession: vi.fn() },
  },
}));

const upsert = vi.fn();
const from = vi.mocked(supabase.from);
const refreshSession = vi.mocked(supabase.auth.refreshSession);

beforeEach(() => {
  upsert.mockReset().mockResolvedValue({ error: null });
  from.mockReset().mockReturnValue({ upsert } as never);
  refreshSession.mockReset().mockResolvedValue({ error: null } as never);
});

describe("becomePromoter", () => {
  it("writes the row the trigger reads, then re-mints the token", async () => {
    await becomePromoter("user-1", "  Sala Apolo  ");

    expect(from).toHaveBeenCalledWith("promoter_profiles");
    expect(upsert).toHaveBeenCalledWith(
      expect.objectContaining({ user_id: "user-1", org_name: "Sala Apolo" }),
      { onConflict: "user_id" },
    );
    expect(refreshSession).toHaveBeenCalledTimes(1);
  });

  it("refuses a blank organisation before touching the database", async () => {
    await expect(becomePromoter("user-1", "   ")).rejects.toThrow(/organisation/);
    expect(upsert).not.toHaveBeenCalled();
  });

  it("does not refresh a token the grant never earned", async () => {
    upsert.mockResolvedValue({ error: { message: "row level security" } });

    await expect(becomePromoter("user-1", "Sala Apolo")).rejects.toThrow("row level security");
    expect(refreshSession).not.toHaveBeenCalled();
  });

  it("retries a failed refresh once — the grant already landed", async () => {
    refreshSession
      .mockResolvedValueOnce({ error: { message: "network" } } as never)
      .mockResolvedValueOnce({ error: null } as never);

    await expect(becomePromoter("user-1", "Sala Apolo")).resolves.toBeUndefined();
    expect(refreshSession).toHaveBeenCalledTimes(2);
  });

  it("tells the two halves apart when the refresh keeps failing", async () => {
    refreshSession.mockResolvedValue({ error: { message: "network" } } as never);

    // Not a plain Error: the row is written, this account *is* a promoter, and
    // the caller has to route somewhere other than the page that reads the
    // stale claim off the token.
    await expect(becomePromoter("user-1", "Sala Apolo")).rejects.toBeInstanceOf(
      PromoterRefreshError,
    );
    expect(upsert).toHaveBeenCalledTimes(1);
    expect(refreshSession).toHaveBeenCalledTimes(2);
  });
});
