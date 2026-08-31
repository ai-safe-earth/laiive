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

export function registerOrgs(app: FastifyInstance, config: GatewayConfig): void {
  const db = createSupabaseAdmin(config);
  const pro = { preHandler: requireRole("pro") };

  /** Orgs this user belongs to, with their seat. One query, reused by all three. */
  async function seatsOf(userId: string): Promise<MemberRow[]> {
    return db.select<MemberRow>(
      "organization_members",
      `select=org_id,role&user_id=eq.${encodeURIComponent(userId)}`,
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
}
