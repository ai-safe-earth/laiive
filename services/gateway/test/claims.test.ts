import type { FastifyInstance } from "fastify";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { buildServer } from "../src/server.js";
import { startSupabaseStub, startUpstreamStub, testConfig } from "./helpers.js";

/**
 * The claim routes (phase D2). `requireRole("pro")` is the floor, never the
 * decision: every test here is about the second check — that this promoter
 * administers the organization they are claiming for — because the service
 * role has already stepped over every RLS policy by the time the route runs.
 */

const OWNER = "d3b07384-d9a0-4c9a-8f4e-000000000001";
const STRANGER = "d3b07384-d9a0-4c9a-8f4e-000000000002";
const PLAIN_MEMBER = "d3b07384-d9a0-4c9a-8f4e-000000000003";
const ORG = "org-1";

let supabase: Awaited<ReturnType<typeof startSupabaseStub>>;
let retriever: Awaited<ReturnType<typeof startUpstreamStub>>;
let app: FastifyInstance;

beforeAll(async () => {
  supabase = await startSupabaseStub();
  retriever = await startUpstreamStub();
  app = await buildServer(testConfig({ supabaseUrl: supabase.url, retrieverUrl: retriever.url }));
  await app.ready();
});

afterAll(async () => {
  await app.close();
  await Promise.all([supabase.close(), retriever.close()]);
});

beforeEach(() => {
  supabase.members.length = 0;
  supabase.ownership.length = 0;
  supabase.members.push(
    { org_id: ORG, user_id: OWNER, role: "owner" },
    { org_id: ORG, user_id: PLAIN_MEMBER, role: "member" },
  );
  retriever.entities.venues.length = 0;
  retriever.entities.venues.push({ uid: "v1", name: "Razzmatazz" });
});

async function post(token: string, body: unknown) {
  return app.inject({
    method: "POST",
    url: "/api/claims",
    headers: { authorization: `Bearer ${token}` },
    payload: body,
  });
}

describe("POST /api/claims", () => {
  it("refuses anonymous and non-pro callers before touching anything", async () => {
    const anon = await app.inject({ method: "POST", url: "/api/claims", payload: {} });
    expect(anon.statusCode).toBe(401);

    const userToken = await supabase.signToken({ sub: OWNER, role: "user" });
    const res = await app.inject({
      method: "POST",
      url: "/api/claims",
      headers: { authorization: `Bearer ${userToken}` },
      payload: { org_id: ORG, entity_type: "venue", entity_uid: "v1" },
    });
    expect(res.statusCode).toBe(403);
    expect(supabase.ownership).toHaveLength(0);
  });

  it("rejects a body that names no entity", async () => {
    const token = await supabase.signToken({ sub: OWNER, role: "pro" });
    expect((await post(token, { entity_type: "venue", entity_uid: "v1" })).statusCode).toBe(400);
    expect((await post(token, { org_id: ORG, entity_type: "city", entity_uid: "v1" })).statusCode).toBe(400);
    expect((await post(token, { org_id: ORG, entity_type: "venue" })).statusCode).toBe(400);
    expect(supabase.ownership).toHaveLength(0);
  });

  it("refuses a pro who does not administer the organization", async () => {
    const token = await supabase.signToken({ sub: STRANGER, role: "pro" });
    const res = await post(token, { org_id: ORG, entity_type: "venue", entity_uid: "v1" });
    expect(res.statusCode).toBe(403);
    expect(supabase.ownership).toHaveLength(0);
  });

  it("refuses a member seat: publishing is not speaking for the org", async () => {
    const token = await supabase.signToken({ sub: PLAIN_MEMBER, role: "pro" });
    const res = await post(token, { org_id: ORG, entity_type: "venue", entity_uid: "v1" });
    expect(res.statusCode).toBe(403);
  });

  it("404s an entity the graph does not have", async () => {
    const token = await supabase.signToken({ sub: OWNER, role: "pro" });
    const res = await post(token, { org_id: ORG, entity_type: "venue", entity_uid: "ghost" });
    expect(res.statusCode).toBe(404);
    expect(supabase.ownership).toHaveLength(0);
  });

  it("records the claim with the graph's name, not the client's", async () => {
    const token = await supabase.signToken({ sub: OWNER, role: "pro" });
    const res = await post(token, {
      org_id: ORG,
      entity_type: "venue",
      entity_uid: "v1",
      entity_name: "Totally My Venue",
    });
    expect(res.statusCode).toBe(201);
    expect(supabase.ownership[0]).toMatchObject({
      org_id: ORG,
      entity_type: "venue",
      entity_uid: "v1",
      basis: "claimed",
      verified: false,
      status: "active",
      claimed_by: OWNER,
      entity_name: "Razzmatazz",
    });
  });

  it("409s a second live claim on the same entity", async () => {
    const token = await supabase.signToken({ sub: OWNER, role: "pro" });
    const body = { org_id: ORG, entity_type: "venue", entity_uid: "v1" };
    expect((await post(token, body)).statusCode).toBe(201);
    const second = await post(token, body);
    expect(second.statusCode).toBe(409);
    expect(supabase.ownership).toHaveLength(1);
  });
});

describe("DELETE /api/claims/:id", () => {
  async function seedClaim() {
    const token = await supabase.signToken({ sub: OWNER, role: "pro" });
    await post(token, { org_id: ORG, entity_type: "venue", entity_uid: "v1" });
    return { token, id: supabase.ownership[0]!["id"] as string };
  }

  it("withdraws by revoking, never by deleting the row", async () => {
    const { token, id } = await seedClaim();
    const res = await app.inject({
      method: "DELETE",
      url: `/api/claims/${id}`,
      headers: { authorization: `Bearer ${token}` },
    });
    expect(res.statusCode).toBe(204);
    // The record that this org once spoke for the venue survives.
    expect(supabase.ownership).toHaveLength(1);
    expect(supabase.ownership[0]).toMatchObject({ status: "revoked", revoked_by: OWNER });
  });

  it("a re-claim after a withdrawal is allowed", async () => {
    const { token, id } = await seedClaim();
    await app.inject({
      method: "DELETE",
      url: `/api/claims/${id}`,
      headers: { authorization: `Bearer ${token}` },
    });
    const again = await post(token, { org_id: ORG, entity_type: "venue", entity_uid: "v1" });
    expect(again.statusCode).toBe(201);
    expect(supabase.ownership).toHaveLength(2);
  });

  it("404s somebody else's claim rather than admitting it exists", async () => {
    const { id } = await seedClaim();
    const stranger = await supabase.signToken({ sub: STRANGER, role: "pro" });
    const res = await app.inject({
      method: "DELETE",
      url: `/api/claims/${id}`,
      headers: { authorization: `Bearer ${stranger}` },
    });
    expect(res.statusCode).toBe(404);
    expect(supabase.ownership[0]).toMatchObject({ status: "active" });
  });

  it("409s a claim that is already revoked", async () => {
    const { token, id } = await seedClaim();
    const url = `/api/claims/${id}`;
    const headers = { authorization: `Bearer ${token}` };
    await app.inject({ method: "DELETE", url, headers });
    const twice = await app.inject({ method: "DELETE", url, headers });
    expect(twice.statusCode).toBe(409);
  });
});

describe("GET /api/claims", () => {
  it("answers three booleans, never whose claim it is", async () => {
    const token = await supabase.signToken({ sub: OWNER, role: "pro" });
    await post(token, { org_id: ORG, entity_type: "venue", entity_uid: "v1" });

    const res = await app.inject({
      method: "GET",
      url: "/api/claims?entity_type=venue&entity_uid=v1",
      headers: { authorization: `Bearer ${token}` },
    });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toMatchObject({
      claimed: true,
      verified: false,
      yours: { org_id: ORG, verified: false },
    });
  });

  it("tells a stranger the entity is claimed without naming the claimant", async () => {
    const owner = await supabase.signToken({ sub: OWNER, role: "pro" });
    await post(owner, { org_id: ORG, entity_type: "venue", entity_uid: "v1" });

    const stranger = await supabase.signToken({ sub: STRANGER, role: "pro" });
    const res = await app.inject({
      method: "GET",
      url: "/api/claims?entity_type=venue&entity_uid=v1",
      headers: { authorization: `Bearer ${stranger}` },
    });
    expect(res.json()).toEqual({ claimed: true, verified: false, yours: null });
    expect(JSON.stringify(res.json())).not.toContain(ORG);
  });

  it("a revoked claim leaves the entity unclaimed", async () => {
    const token = await supabase.signToken({ sub: OWNER, role: "pro" });
    await post(token, { org_id: ORG, entity_type: "venue", entity_uid: "v1" });
    const id = supabase.ownership[0]!["id"] as string;
    await app.inject({
      method: "DELETE",
      url: `/api/claims/${id}`,
      headers: { authorization: `Bearer ${token}` },
    });

    const res = await app.inject({
      method: "GET",
      url: "/api/claims?entity_type=venue&entity_uid=v1",
      headers: { authorization: `Bearer ${token}` },
    });
    expect(res.json()).toEqual({ claimed: false, verified: false, yours: null });
  });

  it("rejects a query naming no entity", async () => {
    const token = await supabase.signToken({ sub: OWNER, role: "pro" });
    const res = await app.inject({
      method: "GET",
      url: "/api/claims?entity_type=venue",
      headers: { authorization: `Bearer ${token}` },
    });
    expect(res.statusCode).toBe(400);
  });
});
