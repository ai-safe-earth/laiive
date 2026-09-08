import type { FastifyInstance } from "fastify";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { buildServer } from "../src/server.js";
import { startSupabaseStub, testConfig } from "./helpers.js";

/**
 * Invitations, gateway-native for the same reason claims are: the table has no
 * INSERT/UPDATE/DELETE policy at all (20260819000011 says sending one and
 * redeeming one both go through the service role), so authorization is entirely
 * these routes' job. `requireRole("pro")` says "some promoter", never "a
 * promoter who runs this org", and every test below is about that gap.
 */
const OWNER = "d3b07384-d9a0-4c9a-8f4e-000000000001";
const STRANGER = "d3b07384-d9a0-4c9a-8f4e-000000000002";
const PLAIN_MEMBER = "d3b07384-d9a0-4c9a-8f4e-000000000003";
const GUEST = "d3b07384-d9a0-4c9a-8f4e-000000000004";
const ORG = "org-1";
const GUEST_EMAIL = "ana@sala.cat";

let supabase: Awaited<ReturnType<typeof startSupabaseStub>>;
let app: FastifyInstance;

beforeAll(async () => {
  supabase = await startSupabaseStub();
  app = await buildServer(testConfig({ supabaseUrl: supabase.url }));
  await app.ready();
});

afterAll(async () => {
  await app.close();
  await supabase.close();
});

beforeEach(() => {
  supabase.members.length = 0;
  supabase.invitations.length = 0;
  supabase.members.push(
    { org_id: ORG, user_id: OWNER, role: "owner" },
    { org_id: ORG, user_id: PLAIN_MEMBER, role: "member" },
  );
});

async function invite(token: string, body: unknown, orgId = ORG) {
  return app.inject({
    method: "POST",
    url: `/api/orgs/${orgId}/invitations`,
    headers: { authorization: `Bearer ${token}` },
    payload: body,
  });
}

async function accept(token: string, body: unknown) {
  return app.inject({
    method: "POST",
    url: "/api/invitations/accept",
    headers: { authorization: `Bearer ${token}` },
    payload: body,
  });
}

/** An invitation for GUEST_EMAIL, and the one-time token it answered with. */
async function seedInvite(role = "member") {
  const token = await supabase.signToken({ sub: OWNER, role: "pro" });
  const res = await invite(token, { email: GUEST_EMAIL, role });
  return { adminToken: token, link: (res.json() as { token: string }).token };
}

describe("POST /api/orgs/:orgId/invitations", () => {
  it("refuses anonymous and non-pro callers before writing anything", async () => {
    const anon = await app.inject({
      method: "POST",
      url: `/api/orgs/${ORG}/invitations`,
      payload: { email: GUEST_EMAIL },
    });
    expect(anon.statusCode).toBe(401);

    const plain = await supabase.signToken({ sub: OWNER, role: "user" });
    expect((await invite(plain, { email: GUEST_EMAIL })).statusCode).toBe(403);
    expect(supabase.invitations).toHaveLength(0);
  });

  it("rejects a body with no usable address or an ungrantable role", async () => {
    const token = await supabase.signToken({ sub: OWNER, role: "pro" });
    expect((await invite(token, {})).statusCode).toBe(400);
    expect((await invite(token, { email: "nope" })).statusCode).toBe(400);
    expect((await invite(token, { email: "@sala.cat" })).statusCode).toBe(400);
    // A valid org_role, but not one a link hands out: transferring an
    // organization is a different act and does not exist yet.
    expect((await invite(token, { email: GUEST_EMAIL, role: "owner" })).statusCode).toBe(400);
    expect((await invite(token, { email: GUEST_EMAIL, role: "wizard" })).statusCode).toBe(400);
    expect(supabase.invitations).toHaveLength(0);
  });

  it("refuses a pro who does not administer the organization", async () => {
    const token = await supabase.signToken({ sub: STRANGER, role: "pro" });
    expect((await invite(token, { email: GUEST_EMAIL })).statusCode).toBe(403);
    expect(supabase.invitations).toHaveLength(0);
  });

  it("refuses a member seat: publishing is not speaking for the org", async () => {
    const token = await supabase.signToken({ sub: PLAIN_MEMBER, role: "pro" });
    expect((await invite(token, { email: GUEST_EMAIL })).statusCode).toBe(403);
    expect(supabase.invitations).toHaveLength(0);
  });

  it("stores a hash, answers with the token exactly once", async () => {
    const token = await supabase.signToken({ sub: OWNER, role: "pro" });
    const res = await invite(token, { email: GUEST_EMAIL, role: "admin" });

    expect(res.statusCode).toBe(201);
    const body = res.json() as { token: string; email: string; role: string };
    expect(body.email).toBe(GUEST_EMAIL);
    expect(body.role).toBe("admin");
    expect(body.token).toMatch(/^[\w-]{40,}$/);

    const row = supabase.invitations[0]!;
    expect(row["org_id"]).toBe(ORG);
    expect(row["invited_by"]).toBe(OWNER);
    // The secret itself must never reach the table: only a SHA-256 of it.
    expect(row["token_hash"]).toMatch(/^[0-9a-f]{64}$/);
    expect(JSON.stringify(row)).not.toContain(body.token);
  });

  it("lowercases the address so the index and the accept check agree", async () => {
    const token = await supabase.signToken({ sub: OWNER, role: "pro" });
    const res = await invite(token, { email: "  Ana@Sala.CAT " });
    expect((res.json() as { email: string }).email).toBe(GUEST_EMAIL);
  });

  it("409s a second live invitation for the same address", async () => {
    const token = await supabase.signToken({ sub: OWNER, role: "pro" });
    expect((await invite(token, { email: GUEST_EMAIL })).statusCode).toBe(201);
    const twice = await invite(token, { email: "ANA@sala.cat" });
    expect(twice.statusCode).toBe(409);
    expect(supabase.invitations).toHaveLength(1);
  });
});

describe("DELETE /api/invitations/:id", () => {
  it("revokes by deleting, so the address can be invited again", async () => {
    const { adminToken } = await seedInvite();
    const id = supabase.invitations[0]!["id"] as string;

    const res = await app.inject({
      method: "DELETE",
      url: `/api/invitations/${id}`,
      headers: { authorization: `Bearer ${adminToken}` },
    });
    expect(res.statusCode).toBe(204);
    expect(supabase.invitations).toHaveLength(0);

    // The point of deleting rather than flagging: the partial unique index
    // covers unaccepted rows, so a kept row would hold the only live slot.
    expect((await invite(adminToken, { email: GUEST_EMAIL })).statusCode).toBe(201);
  });

  it("404s somebody else's invitation rather than admitting it exists", async () => {
    await seedInvite();
    const id = supabase.invitations[0]!["id"] as string;
    const stranger = await supabase.signToken({ sub: STRANGER, role: "pro" });

    const res = await app.inject({
      method: "DELETE",
      url: `/api/invitations/${id}`,
      headers: { authorization: `Bearer ${stranger}` },
    });
    expect(res.statusCode).toBe(404);
    expect(supabase.invitations).toHaveLength(1);
  });

  it("409s one that was already accepted, because that is history", async () => {
    const { adminToken, link } = await seedInvite();
    const guest = await supabase.signToken({ sub: GUEST, role: "user", email: GUEST_EMAIL });
    expect((await accept(guest, { token: link })).statusCode).toBe(200);

    const id = supabase.invitations[0]!["id"] as string;
    const res = await app.inject({
      method: "DELETE",
      url: `/api/invitations/${id}`,
      headers: { authorization: `Bearer ${adminToken}` },
    });
    expect(res.statusCode).toBe(409);
    expect(supabase.invitations).toHaveLength(1);
  });
});

describe("POST /api/invitations/accept", () => {
  it("seats a plain user, who is not a promoter yet and must not have to be", async () => {
    const { link } = await seedInvite("admin");
    // role: "user" on purpose — the trigger from migration 26 grants pro when
    // the seat lands, so requiring pro here would lock out everyone invited.
    const guest = await supabase.signToken({ sub: GUEST, role: "user", email: GUEST_EMAIL });

    const res = await accept(guest, { token: link });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ org_id: ORG, role: "admin", already: false });
    expect(supabase.members).toContainEqual({ org_id: ORG, user_id: GUEST, role: "admin" });
    expect(supabase.invitations[0]!["accepted_by"]).toBe(GUEST);
    expect(supabase.invitations[0]!["accepted_at"]).toBeTruthy();
  });

  it("refuses a link redeemed by an address it was not sent to", async () => {
    const { link } = await seedInvite();
    const other = await supabase.signToken({
      sub: STRANGER,
      role: "user",
      email: "someone@else.com",
    });

    const res = await accept(other, { token: link });
    expect(res.statusCode).toBe(403);
    // The invited address is named so they know which account to sign in as.
    expect(res.json()).toMatchObject({ email: GUEST_EMAIL });
    expect(supabase.members).toHaveLength(2);
  });

  it("matches the address case-insensitively", async () => {
    const { link } = await seedInvite();
    const guest = await supabase.signToken({ sub: GUEST, role: "user", email: "ANA@Sala.Cat" });
    expect((await accept(guest, { token: link })).statusCode).toBe(200);
  });

  it("404s a token nobody issued, and never says more than that", async () => {
    const guest = await supabase.signToken({ sub: GUEST, role: "user", email: GUEST_EMAIL });
    const res = await accept(guest, { token: "not-a-real-token" });
    expect(res.statusCode).toBe(404);
    expect(supabase.members).toHaveLength(2);
  });

  it("409s a token that was already spent", async () => {
    const { link } = await seedInvite();
    const guest = await supabase.signToken({ sub: GUEST, role: "user", email: GUEST_EMAIL });
    expect((await accept(guest, { token: link })).statusCode).toBe(200);

    const twice = await accept(guest, { token: link });
    expect(twice.statusCode).toBe(409);
    expect(supabase.members.filter((row) => row["user_id"] === GUEST)).toHaveLength(1);
  });

  it("410s an expired invitation without seating anyone", async () => {
    const { link } = await seedInvite();
    supabase.invitations[0]!["expires_at"] = new Date(Date.now() - 1000).toISOString();
    const guest = await supabase.signToken({ sub: GUEST, role: "user", email: GUEST_EMAIL });

    const res = await accept(guest, { token: link });
    expect(res.statusCode).toBe(410);
    expect(supabase.members).toHaveLength(2);
  });

  it("refuses a token carrying no email rather than skipping the address check", async () => {
    const { link } = await seedInvite();
    const nameless = await supabase.signToken({ sub: GUEST, role: "user" });
    const res = await accept(nameless, { token: link });
    expect(res.statusCode).toBe(400);
    expect(supabase.members).toHaveLength(2);
  });

  it("requires a signed-in caller and a token", async () => {
    const anon = await app.inject({
      method: "POST",
      url: "/api/invitations/accept",
      payload: { token: "x" },
    });
    expect(anon.statusCode).toBe(401);

    const guest = await supabase.signToken({ sub: GUEST, role: "user", email: GUEST_EMAIL });
    expect((await accept(guest, {})).statusCode).toBe(400);
  });

  it("is idempotent for somebody already seated, and still spends the invitation", async () => {
    const { link } = await seedInvite();
    // The seat exists before the link is redeemed: an admin added them by hand,
    // or a stamp failed after a previous accept had already seated them.
    supabase.members.push({ org_id: ORG, user_id: GUEST, role: "member" });
    const guest = await supabase.signToken({ sub: GUEST, role: "user", email: GUEST_EMAIL });

    const res = await accept(guest, { token: link });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toMatchObject({ already: true });
    expect(supabase.members.filter((row) => row["user_id"] === GUEST)).toHaveLength(1);
    expect(supabase.invitations[0]!["accepted_at"]).toBeTruthy();
  });
});
