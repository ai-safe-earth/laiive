import type { FastifyInstance } from "fastify";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { buildServer } from "../src/server.js";
import { startSupabaseStub, startUpstreamStub, testConfig } from "./helpers.js";

/**
 * PATCH /api/events|venues|artists/:uid — the gateway half of the owner edit
 * path: user_may_edit before the graph write, the entity_edits audit row
 * after it, the pusher's own verdicts passed through untouched.
 */

const PRO = "d3b07384-d9a0-4c9a-8f4e-000000000021";
const ORG = "org-edit-1";

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
      internalApiKey: "sekrit", // pragma: allowlist secret
    }),
  );
  await app.ready();
});

afterAll(async () => {
  await app.close();
  await Promise.all([supabase.close(), pusher.close()]);
});

beforeEach(() => {
  supabase.userMayEdit.value = true;
  supabase.editInserts.length = 0;
  supabase.rpcCalls.length = 0;
  supabase.members.length = 0;
  supabase.ownership.length = 0;
  pusher.seen.length = 0;
  pusher.edit.current = {
    status: 200,
    body: {
      status: "updated",
      uid: "e-1",
      changed: { price_min: { old: 22, new: 10 } },
      warnings: [],
      message: "Event updated.",
    },
  };
});

const patchEvent = async (token?: string, body?: unknown) =>
  app.inject({
    method: "PATCH",
    url: "/api/events/e-1",
    headers: token ? { authorization: `Bearer ${token}` } : {},
    payload: body ?? { fields: { price_min: 10 } },
  });

describe("the authz matrix", () => {
  it("401s anonymous", async () => {
    const response = await patchEvent();
    expect(response.statusCode).toBe(401);
  });

  it("403s a plain user before asking the database anything", async () => {
    const token = await supabase.signToken({ sub: PRO, role: "user" });
    const response = await patchEvent(token);
    expect(response.statusCode).toBe(403);
    expect(supabase.rpcCalls).toHaveLength(0);
  });

  it("403s a pro whose orgs hold no live claim", async () => {
    supabase.userMayEdit.value = false;
    const token = await supabase.signToken({ sub: PRO, role: "pro" });
    const response = await patchEvent(token);
    expect(response.statusCode).toBe(403);
    // the refusal came from user_may_edit, asked with the verified id
    const asked = supabase.rpcCalls.find((call) => call.fn === "user_may_edit");
    expect(asked?.args).toEqual({
      p_entity_type: "event",
      p_entity_uid: "e-1",
      p_uid: PRO,
    });
    // and nothing reached the pusher
    expect(pusher.seen).toHaveLength(0);
  });

  it("lets a member edit, forwards verified headers, and files the audit row", async () => {
    supabase.members.push({ org_id: ORG, user_id: PRO, role: "member" });
    supabase.ownership.push({
      org_id: ORG,
      entity_type: "event",
      entity_uid: "e-1",
      status: "active",
    });
    const token = await supabase.signToken({ sub: PRO, role: "pro" });
    const response = await patchEvent(token, {
      fields: { price_min: 10 },
    });
    expect(response.statusCode).toBe(200);
    expect(response.json().changed).toEqual({ price_min: { old: 22, new: 10 } });

    const upstream = pusher.seen.find((r) => r.method === "PATCH");
    expect(upstream?.url).toBe("/events/e-1");
    expect(upstream?.headers["x-user-id"]).toBe(PRO);
    expect(upstream?.headers["x-internal-key"]).toBe("sekrit");
    expect(JSON.parse(upstream?.body ?? "{}")).toEqual({
      fields: { price_min: 10 },
    });

    expect(supabase.editInserts).toHaveLength(1);
    const [rows] = supabase.editInserts as Record<string, unknown>[][];
    expect(rows[0]).toMatchObject({
      entity_type: "event",
      entity_uid: "e-1",
      org_id: ORG,
      user_id: PRO,
      changes: { price_min: { old: 22, new: 10 } },
    });
  });

  it("admin bypasses user_may_edit and audits with no org", async () => {
    const token = await supabase.signToken({ sub: "admin-1", role: "admin" });
    const response = await patchEvent(token);
    expect(response.statusCode).toBe(200);
    expect(
      supabase.rpcCalls.filter((call) => call.fn === "user_may_edit"),
    ).toHaveLength(0);
    const [rows] = supabase.editInserts as Record<string, unknown>[][];
    expect(rows[0]).toMatchObject({ org_id: null, user_id: "admin-1" });
  });
});

describe("verdicts and plumbing", () => {
  const proToken = async () => {
    supabase.members.push({ org_id: ORG, user_id: PRO, role: "owner" });
    supabase.ownership.push({
      org_id: ORG,
      entity_type: "event",
      entity_uid: "e-1",
      status: "active",
    });
    return supabase.signToken({ sub: PRO, role: "pro" });
  };

  it("passes the pusher's 409 through and files no audit row", async () => {
    pusher.edit.current = {
      status: 409,
      body: { detail: "An event with the same name, date, and venue already exists." },
    };
    const response = await patchEvent(await proToken());
    expect(response.statusCode).toBe(409);
    expect(response.json().detail).toContain("already exists");
    expect(supabase.editInserts).toHaveLength(0);
  });

  it("passes the pusher's 404 through", async () => {
    pusher.edit.current = { status: 404, body: { detail: "No such event." } };
    const response = await patchEvent(await proToken());
    expect(response.statusCode).toBe(404);
  });

  it("400s a body with no fields object", async () => {
    const response = await patchEvent(await proToken(), { price_min: 10 });
    expect(response.statusCode).toBe(400);
    expect(pusher.seen).toHaveLength(0);
  });

  it("files no audit row for a no-op edit", async () => {
    pusher.edit.current = {
      status: 200,
      body: { status: "updated", uid: "e-1", changed: {}, warnings: [] },
    };
    const response = await patchEvent(await proToken());
    expect(response.statusCode).toBe(200);
    expect(supabase.editInserts).toHaveLength(0);
  });

  it("does not shadow the read proxy: GET /api/events?uids= still proxies", async () => {
    pusher.entities.events.push({ uid: "e-1", name: "Jazz Night" });
    const token = await supabase.signToken({ sub: PRO, role: "user" });
    const response = await app.inject({
      method: "GET",
      url: "/api/events?uids=e-1",
      headers: { authorization: `Bearer ${token}` },
    });
    expect(response.statusCode).toBe(200);
    expect(response.json().events).toEqual([{ uid: "e-1", name: "Jazz Night" }]);
  });
});

describe("the kill switch", () => {
  it("503s edit PATCHes while writes are disabled", async () => {
    const paused = await buildServer(
      testConfig({
        supabaseUrl: supabase.url,
        pusherUrl: pusher.url,
        retrieverUrl: pusher.url,
        writesDisabled: true,
      }),
    );
    await paused.ready();
    try {
      const token = await supabase.signToken({ sub: PRO, role: "pro" });
      const response = await paused.inject({
        method: "PATCH",
        url: "/api/events/e-1",
        headers: { authorization: `Bearer ${token}` },
        payload: { fields: { price_min: 10 } },
      });
      expect(response.statusCode).toBe(503);
    } finally {
      await paused.close();
    }
  });
});
