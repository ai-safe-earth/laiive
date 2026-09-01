import { describe, expect, it, vi } from "vitest";
import { fetchClaimState, toMemberships } from "./organizations";

const api = vi.hoisted(() => ({ fetch: vi.fn() }));
vi.mock("@/api/client", () => ({ apiFetch: api.fetch, ApiError: class extends Error {} }));
// The hooks never run here, but the client is imported at module scope, so it
// still has to resolve.
vi.mock("@/auth/supabase", () => ({ supabase: {} }));

const ORG = {
  id: "org-1",
  kind: "venue" as const,
  display_name: "Razzmatazz",
  website: null,
  phone: null,
  contact_email: null,
};

describe("flattening membership rows", () => {
  it("merges the seat onto the organization", () => {
    expect(toMemberships([{ role: "owner", organizations: ORG }])).toEqual([
      { ...ORG, role: "owner" },
    ]);
  });

  it("drops a seat whose organization came back null", () => {
    // Not defensive noise: PostgREST nulls the embedded row when the caller's
    // policies cannot see it, and spreading null would put a nameless,
    // idless entry on the screen with a role attached.
    const rows = [
      { role: "owner", organizations: null },
      { role: "member", organizations: ORG },
    ];
    expect(toMemberships(rows)).toEqual([{ ...ORG, role: "member" }]);
  });

  it("treats a null response as no memberships", () => {
    expect(toMemberships(null)).toEqual([]);
    expect(toMemberships(undefined)).toEqual([]);
  });
});

describe("asking whether an entity is already spoken for", () => {
  it("escapes both parameters rather than letting a uid end the query", async () => {
    api.fetch.mockClear();
    api.fetch.mockResolvedValue({
      json: () => Promise.resolve({ claimed: false, verified: false, yours: null }),
    });

    await fetchClaimState("venue", "v1&entity_type=event");

    expect(api.fetch).toHaveBeenCalledWith(
      "/api/claims?entity_type=venue&entity_uid=v1%26entity_type%3Devent",
    );
  });

  it("passes the gateway's three booleans through unchanged", async () => {
    api.fetch.mockResolvedValue({
      json: () =>
        Promise.resolve({
          claimed: true,
          verified: true,
          yours: { id: "c1", org_id: "org-1", verified: true },
        }),
    });

    await expect(fetchClaimState("artist", "a1")).resolves.toEqual({
      claimed: true,
      verified: true,
      yours: { id: "c1", org_id: "org-1", verified: true },
    });
  });
});
