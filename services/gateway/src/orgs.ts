import { createHash, randomBytes } from "node:crypto";
import type { FastifyInstance, FastifyRequest } from "fastify";
import { requireRole } from "./auth.js";
import type { GatewayConfig } from "./config.js";
import { createSupabaseAdmin, PostgrestError } from "./supabaseAdmin.js";

/**
 * Claiming, gateway-native (phase D2).
 *
 * Why native rather than direct-to-Supabase under RLS, which is how the reads
 * in `frontend/src/api/profile.ts` work: recording a claim needs two facts
 * PostgREST cannot check in a policy — that the caller administers the
 * organization they are claiming *for*, and that the entity they name exists
 * in the graph, which lives in Neo4j behind the retriever. Both are lookups
 * across two systems, so the decision lives in one place that can see both.
 *
 * `requireRole("pro")` is necessary and nowhere near sufficient here: it says
 * "some promoter", not "a promoter who runs this org". Every route below does
 * its own membership check, because the service-role key has already stepped
 * over the row-level rules by the time it is used.
 */

const ENTITY_TYPES = new Set(["venue", "artist", "event"]);

/** The graph lookup a claim is checked against, per entity type. */
const LOOKUP_PATH: Record<string, string> = {
  venue: "venues",
  artist: "artists",
  event: "events",
};

interface OwnershipRow {
  id: string;
  org_id: string;
  entity_type: string;
  entity_uid: string;
  verified: boolean;
  status: string;
  entity_name: string | null;
}

interface MemberRow {
  org_id: string;
  role: string;
}

/** The seats an invitation may offer. Deliberately not `owner` — see the route. */
const INVITABLE_ROLES = new Set(["admin", "member"]);

/** Fourteen days, matching the column default in 20260819000011. */
const INVITE_TTL_MS = 14 * 24 * 60 * 60 * 1000;

interface InvitationRow {
  id: string;
  org_id: string;
  email: string;
  role: string;
  expires_at: string;
  accepted_at: string | null;
}

/** What the pusher answers /validate-event with, plus phase D's creation facts. */
interface PublishResult {
  success: boolean;
  event_id: string | null;
  event_name: string | null;
  venue: string | null;
  warnings: string[];
  venue_uid: string | null;
  venue_created: boolean;
  artist_uids_created: string[];
}

export function registerOrgs(app: FastifyInstance, config: GatewayConfig): void {
  const db = createSupabaseAdmin(config);
  const pro = { preHandler: requireRole("pro") };

  /**
   * Orgs this user belongs to, with their seat. One query, reused by all three.
   *
   * Ordered, and that is not cosmetic. `orgForPublish` falls back to `seats[0]`
   * when the caller names no organization, and PostgREST returns rows in
   * whatever order the heap gives without an `order` — so for somebody in two
   * organizations, every publish was filed against an arbitrary one, and the
   * one `/pro/org` was showing had no reason to be it. Oldest first, so the
   * fallback is "the organization you founded first" rather than a coin toss.
   */
  async function seatsOf(userId: string): Promise<MemberRow[]> {
    return db.select<MemberRow>(
      "organization_members",
      `select=org_id,role&user_id=eq.${encodeURIComponent(userId)}&order=created_at.asc`,
    );
  }

  /**
   * The entity's name as the graph spells it, or null when no such uid exists.
   *
   * Both questions in one call: existence, and the display name that gets
   * denormalized onto the claim. Taking the name from the request body instead
   * would let a promoter choose the label a reviewer sees next to their claim.
   */
  async function resolveEntityName(
    type: string,
    uid: string,
    request: FastifyRequest,
  ): Promise<string | null> {
    const path = LOOKUP_PATH[type];
    if (!path) return null;
    const url = `${config.retrieverUrl}/${path}?uids=${encodeURIComponent(uid)}`;
    const headers: Record<string, string> = {};
    if (config.internalApiKey) headers["x-internal-key"] = config.internalApiKey;

    const response = await fetch(url, { headers });
    if (!response.ok) {
      request.log.error({ status: response.status, type }, "entity lookup failed");
      throw new Error("entity lookup failed");
    }
    const body = (await response.json()) as Record<string, { name?: string }[]>;
    const hits = body[path] ?? body["events"] ?? [];
    return hits[0]?.name ?? null;
  }

  // ── POST /api/claims ──────────────────────────────────────────────────────

  app.post("/api/claims", pro, async (request, reply) => {
    const user = request.user;
    if (!user) return reply.code(401).send({ error: "authentication required" });

    const body = request.body as {
      org_id?: unknown;
      entity_type?: unknown;
      entity_uid?: unknown;
    } | null;
    const orgId = body?.org_id;
    const entityType = body?.entity_type;
    const entityUid = body?.entity_uid;

    if (typeof orgId !== "string" || orgId.length === 0) {
      return reply.code(400).send({ error: "org_id required" });
    }
    if (typeof entityType !== "string" || !ENTITY_TYPES.has(entityType)) {
      return reply.code(400).send({ error: "entity_type must be venue, artist or event" });
    }
    if (typeof entityUid !== "string" || entityUid.length === 0 || entityUid.length > 128) {
      return reply.code(400).send({ error: "entity_uid required" });
    }

    // A pro may only claim for an organization they administer. Membership
    // alone is not enough: a `member` seat can publish, not speak for the org.
    const seats = await seatsOf(user.id);
    const seat = seats.find((row) => row.org_id === orgId);
    if (!seat || (seat.role !== "owner" && seat.role !== "admin")) {
      return reply.code(403).send({ error: "you do not administer that organization" });
    }

    let entityName: string | null;
    try {
      entityName = await resolveEntityName(entityType, entityUid, request);
    } catch {
      return reply.code(502).send({ error: "could not check the entity" });
    }
    if (entityName === null) {
      return reply.code(404).send({ error: "no such entity" });
    }

    try {
      const row = await db.insert<OwnershipRow>("entity_ownership", {
        org_id: orgId,
        entity_type: entityType,
        entity_uid: entityUid,
        basis: "claimed",
        verified: false,
        status: "active",
        claimed_by: user.id,
        entity_name: entityName,
      });
      return reply.code(201).send(row);
    } catch (error) {
      if (error instanceof PostgrestError && error.isUniqueViolation) {
        // The partial unique index only covers active rows, so this is
        // precisely "you already hold a live claim on this", not "you once did".
        return reply.code(409).send({ error: "this organization already claims that entity" });
      }
      request.log.error({ err: error }, "claim insert failed");
      return reply.code(502).send({ error: "claim not recorded" });
    }
  });

  // ── DELETE /api/claims/:id ────────────────────────────────────────────────

  app.delete<{ Params: { id: string } }>(
    "/api/claims/:id",
    pro,
    async (request, reply) => {
      const user = request.user;
      if (!user) return reply.code(401).send({ error: "authentication required" });

      const { id } = request.params;
      let claims: OwnershipRow[];
      try {
        claims = await db.select<OwnershipRow>(
          "entity_ownership",
          `select=id,org_id,entity_type,entity_uid,verified,status,entity_name&id=eq.${encodeURIComponent(id)}`,
        );
      } catch (error) {
        request.log.error({ err: error }, "claim read failed");
        return reply.code(502).send({ error: "could not read the claim" });
      }

      const claim = claims[0];
      // 404 rather than 403 for a claim they cannot administer: whether a given
      // uuid names somebody else's claim is not theirs to learn.
      const seats = await seatsOf(user.id);
      const seat = claim ? seats.find((row) => row.org_id === claim.org_id) : undefined;
      if (!claim || !seat || (seat.role !== "owner" && seat.role !== "admin")) {
        return reply.code(404).send({ error: "no such claim" });
      }
      if (claim.status !== "active") {
        return reply.code(409).send({ error: "that claim is not active" });
      }

      try {
        // Withdrawal is a revoke, not a delete: the row is the record that this
        // organization once spoke for the entity, and an admin reviewing a
        // later claim needs to see it.
        await db.patch("entity_ownership", `id=eq.${encodeURIComponent(id)}`, {
          status: "revoked",
          revoked_by: user.id,
          revoked_at: new Date().toISOString(),
          revoke_note: "withdrawn by the organization",
        });
      } catch (error) {
        request.log.error({ err: error }, "claim withdrawal failed");
        return reply.code(502).send({ error: "claim not withdrawn" });
      }
      return reply.code(204).send();
    },
  );

  // ── GET /api/claims ───────────────────────────────────────────────────────

  app.get("/api/claims", pro, async (request, reply) => {
    const user = request.user;
    if (!user) return reply.code(401).send({ error: "authentication required" });

    const query = request.query as { entity_type?: unknown; entity_uid?: unknown };
    const entityType = query.entity_type;
    const entityUid = query.entity_uid;

    if (typeof entityType !== "string" || !ENTITY_TYPES.has(entityType)) {
      return reply.code(400).send({ error: "entity_type must be venue, artist or event" });
    }
    if (typeof entityUid !== "string" || entityUid.length === 0) {
      return reply.code(400).send({ error: "entity_uid required" });
    }

    let rows: OwnershipRow[];
    try {
      rows = await db.select<OwnershipRow>(
        "entity_ownership",
        `select=id,org_id,entity_type,entity_uid,verified,status,entity_name` +
          `&entity_type=eq.${encodeURIComponent(entityType)}` +
          `&entity_uid=eq.${encodeURIComponent(entityUid)}` +
          `&status=eq.active`,
      );
    } catch (error) {
      request.log.error({ err: error }, "claims read failed");
      return reply.code(502).send({ error: "could not read the claims" });
    }

    // Three booleans, no rows: who else claims this entity is not the caller's
    // business, only whether the door is open and whether they are behind it.
    const seats = await seatsOf(user.id);
    const mine = new Set(seats.map((row) => row.org_id));
    const yours = rows.find((row) => mine.has(row.org_id));
    return reply.send({
      claimed: rows.length > 0,
      verified: rows.some((row) => row.verified),
      yours: yours ? { id: yours.id, org_id: yours.org_id, verified: yours.verified } : null,
    });
  });

  // ── Invitations ───────────────────────────────────────────────────────────

  /**
   * The token is a secret the database never learns.
   *
   * `organization_invitations` stores only a SHA-256 of it, which is what makes
   * a leaked table row worthless: 32 random bytes are not guessable and the
   * hash is not reversible. So the raw token exists in exactly one response
   * body, once, and is unrecoverable afterwards — revoke and re-invite is the
   * only way back to a live link, which is deliberate.
   *
   * Plain SHA-256 rather than a password KDF on purpose: this is a
   * high-entropy random value, not a human-chosen secret, so there is nothing
   * for bcrypt's work factor to defend against.
   */
  const hashToken = (token: string) => createHash("sha256").update(token).digest("hex");

  /** The caller's seat in an org, or undefined — the admin check every route repeats. */
  async function adminSeat(userId: string, orgId: string): Promise<MemberRow | undefined> {
    const seats = await seatsOf(userId);
    const seat = seats.find((row) => row.org_id === orgId);
    if (!seat || (seat.role !== "owner" && seat.role !== "admin")) return undefined;
    return seat;
  }

  // ── POST /api/orgs/:orgId/invitations ─────────────────────────────────────

  app.post<{ Params: { orgId: string } }>(
    "/api/orgs/:orgId/invitations",
    pro,
    async (request, reply) => {
      const user = request.user;
      if (!user) return reply.code(401).send({ error: "authentication required" });

      const { orgId } = request.params;
      const body = request.body as { email?: unknown; role?: unknown } | null;
      const rawEmail = body?.email;
      const role = body?.role ?? "member";

      // Lowercased here because the partial unique index is on lower(email) and
      // the accept route compares addresses case-insensitively — storing the
      // typed casing would make the row disagree with both.
      const email = typeof rawEmail === "string" ? rawEmail.trim().toLowerCase() : "";
      // The same shape the column's own check constraint enforces, refused here
      // so the caller gets a sentence rather than a 502 from a violated check.
      if (!email || email.length > 254 || email.indexOf("@") < 1) {
        return reply.code(400).send({ error: "a valid email is required" });
      }
      if (typeof role !== "string" || !INVITABLE_ROLES.has(role)) {
        // `owner` is a valid org_role but not something to hand out by link:
        // transferring an organization is a different act with different
        // consequences, and it does not exist yet.
        return reply.code(400).send({ error: "role must be admin or member" });
      }

      // A member seat may publish, not speak for the org — the same line
      // POST /api/claims draws, for the same reason.
      if (!(await adminSeat(user.id, orgId))) {
        return reply.code(403).send({ error: "you do not administer that organization" });
      }

      const token = randomBytes(32).toString("base64url");
      let row: InvitationRow;
      try {
        row = await db.insert<InvitationRow>("organization_invitations", {
          org_id: orgId,
          email,
          role,
          token_hash: hashToken(token),
          invited_by: user.id,
          expires_at: new Date(Date.now() + INVITE_TTL_MS).toISOString(),
        });
      } catch (error) {
        if (error instanceof PostgrestError && error.isUniqueViolation) {
          // The index only covers unaccepted rows, so this is precisely "that
          // address already has a live invitation here", not "it once did".
          return reply.code(409).send({ error: "that address already has a pending invitation" });
        }
        request.log.error({ err: error }, "invitation insert failed");
        return reply.code(502).send({ error: "invitation not created" });
      }

      // The only time the token is ever readable. The gateway does not build
      // the link: it does not know which origin the SPA is served from, and
      // the browser holding this response does.
      return reply.code(201).send({
        id: row.id,
        email: row.email,
        role: row.role,
        expires_at: row.expires_at,
        token,
      });
    },
  );

  // ── DELETE /api/invitations/:id ───────────────────────────────────────────

  app.delete<{ Params: { id: string } }>(
    "/api/invitations/:id",
    pro,
    async (request, reply) => {
      const user = request.user;
      if (!user) return reply.code(401).send({ error: "authentication required" });

      const { id } = request.params;
      let rows: InvitationRow[];
      try {
        rows = await db.select<InvitationRow>(
          "organization_invitations",
          `select=id,org_id,email,role,expires_at,accepted_at&id=eq.${encodeURIComponent(id)}`,
        );
      } catch (error) {
        request.log.error({ err: error }, "invitation read failed");
        return reply.code(502).send({ error: "could not read the invitation" });
      }

      // 404 rather than 403 for one they cannot administer: whether a given
      // uuid names somebody else's invitation is not theirs to learn. Same
      // reasoning as DELETE /api/claims/:id.
      const invitation = rows[0];
      if (!invitation || !(await adminSeat(user.id, invitation.org_id))) {
        return reply.code(404).send({ error: "no such invitation" });
      }
      if (invitation.accepted_at) {
        // Accepted invitations are history and stay. Removing the person is a
        // different act on a different table, and not one this route does.
        return reply.code(409).send({ error: "that invitation was already accepted" });
      }

      try {
        await db.del("organization_invitations", `id=eq.${encodeURIComponent(id)}`);
      } catch (error) {
        request.log.error({ err: error }, "invitation revoke failed");
        return reply.code(502).send({ error: "invitation not revoked" });
      }
      return reply.code(204).send();
    },
  );

  // ── POST /api/invitations/accept ──────────────────────────────────────────

  /**
   * Redeeming a link. Open to any signed-in account, not just promoters: the
   * whole point is that the person being invited usually is not one yet, and
   * the trigger from 20260908000026 grants the role when the seat lands.
   */
  app.post("/api/invitations/accept", { preHandler: requireRole("user") }, async (request, reply) => {
    const user = request.user;
    if (!user) return reply.code(401).send({ error: "authentication required" });

    const body = request.body as { token?: unknown } | null;
    const token = body?.token;
    if (typeof token !== "string" || token.length === 0 || token.length > 256) {
      return reply.code(400).send({ error: "token required" });
    }
    if (!user.email) {
      // Every sign-in this product offers carries an email claim, so this is a
      // token shape nobody should have. Refuse rather than skip the check that
      // binds a link to the address it was sent to.
      return reply.code(400).send({ error: "this account has no email address" });
    }

    let rows: InvitationRow[];
    try {
      rows = await db.select<InvitationRow>(
        "organization_invitations",
        `select=id,org_id,email,role,expires_at,accepted_at` +
          `&token_hash=eq.${encodeURIComponent(hashToken(token))}`,
      );
    } catch (error) {
      request.log.error({ err: error }, "invitation lookup failed");
      return reply.code(502).send({ error: "could not check the invitation" });
    }

    const invitation = rows[0];
    if (!invitation) return reply.code(404).send({ error: "no such invitation" });
    if (invitation.accepted_at) {
      return reply.code(409).send({ error: "that invitation was already accepted" });
    }
    if (Date.parse(invitation.expires_at) <= Date.now()) {
      return reply.code(410).send({ error: "that invitation has expired" });
    }
    if (invitation.email.toLowerCase() !== user.email.toLowerCase()) {
      // The address goes in the message, not just beside it: the client shows
      // `error` verbatim, and the useful thing to tell whoever holds this link
      // is which account to sign in as. They were sent it — it is not a leak.
      return reply.code(403).send({
        error: `that invitation was sent to ${invitation.email}`,
        email: invitation.email,
      });
    }

    // Seat first, stamp second. A stamp that fails leaves a live invitation and
    // a real seat, and re-accepting is idempotent below; the reverse order
    // burns the invitation and leaves the person outside the organization with
    // no way back in. Same argument as recording ownership after the graph
    // write in /api/publish.
    const seats = await seatsOf(user.id);
    const already = seats.some((row) => row.org_id === invitation.org_id);
    if (!already) {
      try {
        await db.insert("organization_members", {
          org_id: invitation.org_id,
          user_id: user.id,
          role: invitation.role,
        });
      } catch (error) {
        request.log.error({ err: error }, "membership insert failed");
        return reply.code(502).send({ error: "could not add you to the organization" });
      }
    }

    try {
      await db.patch("organization_invitations", `id=eq.${encodeURIComponent(invitation.id)}`, {
        accepted_at: new Date().toISOString(),
        accepted_by: user.id,
      });
    } catch (error) {
      // The seat is what matters and it exists. Say so rather than 500 over the
      // bookkeeping half — the invitation stays live and the next attempt takes
      // the `already` branch above.
      request.log.error({ err: error }, "invitation not stamped accepted");
    }

    return reply.send({ org_id: invitation.org_id, role: invitation.role, already });
  });

  // ── POST /api/publish ─────────────────────────────────────────────────────

  /**
   * The organization a publish should be recorded against, creating one if the
   * promoter has none.
   *
   * Lazy bootstrap rather than a screen that blocks publishing: a promoter who
   * never opened /pro/org still owns what they publish, and the alternative -
   * recording nothing - is the failure that cannot be repaired later, because
   * nothing afterwards knows the event was theirs.
   *
   * The RPC runs as the user, not as the service role: it reads auth.uid() for
   * the pro floor and the owner seat, and under the service key that is NULL.
   */
  async function orgForPublish(
    userId: string,
    accessToken: string | undefined,
    request: FastifyRequest,
    /** The organization the publisher named, already checked against their seats. */
    chosen?: string,
  ): Promise<string | null> {
    if (chosen) return chosen;
    const seats = await seatsOf(userId);
    if (seats[0]) return seats[0].org_id;
    if (!accessToken) return null;

    const profiles = await db.select<{ org_name: string | null }>(
      "promoter_profiles",
      `select=org_name&user_id=eq.${encodeURIComponent(userId)}`,
    );
    const name = profiles[0]?.org_name?.trim();
    if (!name) return null;

    try {
      return await db.rpcAsUser<string>(
        "create_organization",
        { p_kind: "promoter", p_display_name: name },
        accessToken,
      );
    } catch (error) {
      request.log.error({ err: error }, "lazy organization bootstrap failed");
      return null;
    }
  }

  /** Names for the artists this write created, as the graph spells them. */
  async function artistNames(uids: string[]): Promise<Record<string, string>> {
    if (!uids.length) return {};
    const headers: Record<string, string> = {};
    if (config.internalApiKey) headers["x-internal-key"] = config.internalApiKey;
    const url = `${config.retrieverUrl}/artists?uids=${encodeURIComponent(uids.join(","))}`;
    const response = await fetch(url, { headers });
    if (!response.ok) return {};
    const body = (await response.json()) as { artists?: { uid: string; name: string }[] };
    return Object.fromEntries((body.artists ?? []).map((a) => [a.uid, a.name]));
  }

  app.post("/api/publish", pro, async (request, reply) => {
    const user = request.user;
    if (!user) return reply.code(401).send({ error: "authentication required" });

    // Which organization this is being published for. Checked here, before the
    // graph write, because it is the only point where refusing is still free —
    // ownership is recorded afterwards, and by then the event exists.
    //
    // Membership, not administration: a `member` seat may publish for the org,
    // it just may not speak for it on a claim. That is the line 20260819000011
    // draws and this route keeps it.
    const { org_id: namedOrg, ...forwarded } = (request.body ?? {}) as Record<string, unknown>;
    let chosenOrg: string | undefined;
    if (namedOrg !== undefined) {
      if (typeof namedOrg !== "string" || namedOrg.length === 0) {
        return reply.code(400).send({ error: "org_id must be an organization id" });
      }
      const seats = await seatsOf(user.id);
      if (!seats.some((seat) => seat.org_id === namedOrg)) {
        return reply.code(403).send({ error: "you do not belong to that organization" });
      }
      chosenOrg = namedOrg;
    }

    const headers: Record<string, string> = {
      "content-type": "application/json",
      "x-user-id": user.id,
      "x-user-role": user.role,
      "x-request-id": String(request.id),
    };
    if (config.internalApiKey) headers["x-internal-key"] = config.internalApiKey;

    let upstream: Response;
    try {
      upstream = await fetch(`${config.pusherUrl}/validate-event`, {
        method: "POST",
        headers,
        // Without org_id: it is the gateway's business, and the pusher's
        // request model would reject a field it does not know about.
        body: JSON.stringify(forwarded),
      });
    } catch (error) {
      request.log.error({ err: error }, "publish upstream unreachable");
      return reply.code(502).send({ error: "could not publish that" });
    }

    const body: unknown = await upstream.json().catch(() => null);
    // The pusher owns the verdict on the draft - 422 for a missing field, 409
    // for a duplicate - so its status passes straight through rather than
    // being reinterpreted here.
    if (!upstream.ok) return reply.code(upstream.status).send(body ?? {});

    const result = body as PublishResult;
    const warnings = [...(result.warnings ?? [])];

    // Ownership is recorded after the graph write, never before: a claim on an
    // event that failed to publish is worse than no claim at all. A failure
    // here leaves the event published and says so, rather than 500ing over a
    // write the promoter already succeeded at.
    try {
      const orgId = await orgForPublish(user.id, bearer(request), request, chosenOrg);
      if (!orgId) {
        warnings.push("Published, but not recorded against an organisation yet.");
      } else {
        const names = await artistNames(result.artist_uids_created ?? []);
        const rows: Record<string, unknown>[] = [];
        const own = (type: string, uid: string, name: string | null) =>
          rows.push({
            org_id: orgId,
            entity_type: type,
            entity_uid: uid,
            basis: "created",
            // `created` needs no review: you made the thing. The migration's
            // created_is_verified check enforces the pair.
            verified: true,
            status: "active",
            claimed_by: user.id,
            entity_name: name,
          });

        if (result.event_id) own("event", result.event_id, result.event_name);
        if (result.venue_created && result.venue_uid) {
          own("venue", result.venue_uid, result.venue);
        }
        for (const uid of result.artist_uids_created ?? []) {
          own("artist", uid, names[uid] ?? null);
        }
        // One insert, so a partial record is not a state this can end in.
        if (rows.length) await db.insert("entity_ownership", rows);
      }
    } catch (error) {
      request.log.error({ err: error }, "ownership not recorded for publish");
      warnings.push("Published, but ownership was not recorded.");
    }

    return reply.code(upstream.status).send({ ...result, warnings });
  });
}

/** The caller's raw access token, which the RPC bootstrap runs as. */
function bearer(request: FastifyRequest): string | undefined {
  const header = request.headers.authorization;
  if (!header) return undefined;
  const [scheme, token] = header.split(" ");
  return scheme?.toLowerCase() === "bearer" && token ? token : undefined;
}
