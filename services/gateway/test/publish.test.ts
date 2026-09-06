import type { FastifyInstance } from "fastify";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { buildServer } from "../src/server.js";
import { startSupabaseStub, startUpstreamStub, testConfig } from "./helpers.js";

/**
 * POST /api/publish — the wrapper that turns "an event was written" into "this
 * organization owns it". The publish itself belongs to the pusher; what is
 * tested here is what the gateway records afterwards, and what it refuses to
 * record.
 */

const PRO = "d3b07384-d9a0-4c9a-8f4e-000000000010";
const ORG = "org-1";

let supabase: Awaited<ReturnType<typeof startSupabaseStub>>;
let pusher: Awaited<ReturnType<typeof startUpstreamStub>>;
let app: FastifyInstance;

beforeAll(async () => {
  supabase = await startSupabaseStub();
  pusher = await startUpstreamStub();
  app = await buildServer(
    testConfig({
      supabaseUrl: supabase.url,
      pusherUrl: pusher.url,
      retrieverUrl: pusher.url,
    }),
  );
  await app.ready();
});

afterAll(async () => {
  await app.close();
  await Promise.all([supabase.close(), pusher.close()]);
});

/** A pusher answer for an event at a brand-new venue with one new artist. */
function published(overrides: Record<string, unknown> = {}) {
  return {
    status: 200,
    body: {
      success: true,
      event_id: "e1",
      event_name: "Jazz Night",
      venue: "Quasimodo",
      warnings: [],
      venue_uid: "v-new",
      venue_created: true,
      artist_uids_created: ["a-new"],
      ...overrides,
    },
  };
}

beforeEach(() => {
  supabase.members.length = 0;
  supabase.ownership.length = 0;
  supabase.promoterProfiles.length = 0;
  supabase.rpcCalls.length = 0;
  pusher.entities.artists.length = 0;
  pusher.entities.artists.push({ uid: "a-new", name: "Ana Beck Quartet" });
  pusher.publish.current = published();
  supabase.members.push({ org_id: ORG, user_id: PRO, role: "owner" });
});

async function publish(token: string) {
  return app.inject({
    method: "POST",
    url: "/api/publish",
    headers: { authorization: `Bearer ${token}` },
    payload: { draft: { artists: ["Ana Beck Quartet"] } },
  });
}

describe("POST /api/publish", () => {
  it("refuses anonymous and plain users before reaching the pusher", async () => {
    expect((await app.inject({ method: "POST", url: "/api/publish" })).statusCode).toBe(401);
    const userToken = await supabase.signToken({ sub: PRO, role: "user" });
    expect((await publish(userToken)).statusCode).toBe(403);
    expect(supabase.ownership).toHaveLength(0);
  });

  it("records the event, the venue it created and the artist it created", async () => {
    const token = await supabase.signToken({ sub: PRO, role: "pro" });
    const res = await publish(token);

    expect(res.statusCode).toBe(200);
    expect(supabase.ownership).toHaveLength(3);
    expect(supabase.ownership).toContainEqual(
      expect.objectContaining({
        org_id: ORG,
        entity_type: "event",
        entity_uid: "e1",
        basis: "created",
        verified: true,
        status: "active",
        entity_name: "Jazz Night",
      }),
    );
    expect(supabase.ownership).toContainEqual(
      expect.objectContaining({ entity_type: "venue", entity_uid: "v-new" }),
    );
    // The artist's name comes from the graph, not from the draft the client sent.
    expect(supabase.ownership).toContainEqual(
      expect.objectContaining({
        entity_type: "artist",
        entity_uid: "a-new",
        entity_name: "Ana Beck Quartet",
      }),
    );
  });

  it("does not hand over a venue this publish merely named", async () => {
    // Publishing at somebody else's room is not a claim on the room — the
    // whole point of venue_created.
    pusher.publish.current = published({ venue_created: false, venue_uid: "v-existing" });
    const token = await supabase.signToken({ sub: PRO, role: "pro" });
    await publish(token);

    expect(supabase.ownership.map((row) => row["entity_type"])).toEqual(["event", "artist"]);
  });

  it("does not hand over an artist that already existed", async () => {
    pusher.publish.current = published({ artist_uids_created: [] });
    const token = await supabase.signToken({ sub: PRO, role: "pro" });
    await publish(token);

    expect(supabase.ownership.map((row) => row["entity_type"])).toEqual(["event", "venue"]);
  });

  it("bootstraps an organisation, as the user, for a promoter who has none", async () => {
    supabase.members.length = 0;
    supabase.promoterProfiles.push({ user_id: PRO, org_name: "Sala Apolo" });
    const token = await supabase.signToken({ sub: PRO, role: "pro" });

    const res = await publish(token);

    expect(res.statusCode).toBe(200);
    expect(supabase.rpcCalls).toHaveLength(1);
    expect(supabase.rpcCalls[0]).toMatchObject({
      fn: "create_organization",
      args: { p_kind: "promoter", p_display_name: "Sala Apolo" },
    });
    // As the user, never as the service role: create_organization reads
    // auth.uid() for the pro floor and the owner seat.
    expect(supabase.rpcCalls[0]!.authorization).toBe(`Bearer ${token}`);
    expect(supabase.ownership.length).toBeGreaterThan(0);
  });

  it("still publishes when there is nothing to record against, and says so", async () => {
    supabase.members.length = 0; // no org, and no promoter profile to name one
    const token = await supabase.signToken({ sub: PRO, role: "pro" });

    const res = await publish(token);

    expect(res.statusCode).toBe(200);
    expect(supabase.ownership).toHaveLength(0);
    expect(res.json().warnings.join(" ")).toContain("organisation");
  });

  it("passes the pusher's own verdict through untouched", async () => {
    // 409 duplicate and 422 incomplete are the pusher's calls, not the
    // gateway's, and reinterpreting them would lose the message.
    pusher.publish.current = { status: 409, body: { detail: "already exists" } };
    const token = await supabase.signToken({ sub: PRO, role: "pro" });

    const res = await publish(token);

    expect(res.statusCode).toBe(409);
    expect(res.json()).toEqual({ detail: "already exists" });
    expect(supabase.ownership).toHaveLength(0);
  });

  it("forwards the verified identity and the internal key to the pusher", async () => {
    const token = await supabase.signToken({ sub: PRO, role: "pro" });
    await publish(token);

    const forwarded = pusher.seen.find((r) => r.url === "/validate-event");
    expect(forwarded?.headers["x-user-id"]).toBe(PRO);
    expect(forwarded?.headers["x-user-role"]).toBe("pro");
    expect(forwarded?.headers["authorization"]).toBeUndefined();
  });
});

/**
 * WRITES_DISABLED — the write kill switch. The graph writer has no delete path,
 * so pausing writes is the only reversible move there is when publishing goes
 * wrong. It sits at the gateway because the pusher and search write paths do
 * not meet anywhere else, and it must leave reads alone: a switch that also
 * kills chat is a worse outage than whatever made you reach for it.
 */
describe("WRITES_DISABLED", () => {
  const ADMIN = "d3b07384-d9a0-4c9a-8f4e-000000000011";
  let paused: FastifyInstance;

  beforeAll(async () => {
    paused = await buildServer(
      testConfig({
        supabaseUrl: supabase.url,
        pusherUrl: pusher.url,
        retrieverUrl: pusher.url,
        searchUrl: pusher.url,
        searchEnabled: true,
        writesDisabled: true,
      }),
    );
    await paused.ready();
  });

  afterAll(async () => {
    await paused.close();
  });

  it("503s every graph-write route and reaches no writer", async () => {
    const proToken = await supabase.signToken({ sub: PRO, role: "pro" });
    const adminToken = await supabase.signToken({ sub: ADMIN, role: "admin" });
    pusher.seen.length = 0;

    const routes: [string, string][] = [
      ["/api/publish", proToken],
      ["/api/push/validate-event", proToken],
      ["/api/admin/search/reports/r1/approve", adminToken],
      ["/api/admin/search/backfill", adminToken],
    ];

    for (const [url, token] of routes) {
      const res = await paused.inject({
        method: "POST",
        url,
        headers: { authorization: `Bearer ${token}` },
        payload: {},
      });
      expect(res.statusCode, url).toBe(503);
      expect(res.json(), url).toEqual({ error: "publishing is paused" });
    }

    // The assertion that matters: nothing got past the gateway to the writer.
    expect(pusher.seen.filter((r) => r.url === "/validate-event")).toHaveLength(0);
  });

  it("leaves chat and reads serving", async () => {
    const token = await supabase.signToken({ sub: PRO, role: "pro" });
    const res = await paused.inject({
      method: "POST",
      url: "/api/chat",
      headers: { authorization: `Bearer ${token}` },
      payload: { message: "que hay el viernes" },
    });
    expect(res.statusCode).not.toBe(503);
  });

  it("keeps writing when the flag is unset — a typo must not pause publishing", async () => {
    const token = await supabase.signToken({ sub: PRO, role: "pro" });
    expect((await publish(token)).statusCode).toBe(200);
  });
});
