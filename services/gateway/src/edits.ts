import type { FastifyInstance } from "fastify";
import type { GatewayConfig } from "./config.js";
import { requireRole } from "./auth.js";
import { createSupabaseAdmin, type SupabaseAdmin } from "./supabaseAdmin.js";

/**
 * Owner edit routes (Phase E). Native routes in the /api/publish mould, never
 * proxies: the decision needs facts from two systems — Supabase (does the
 * caller's org hold a live claim: user_may_edit, migration 22's one question)
 * and the graph (the pusher performs the write) — so it lives in the one
 * place that can see both. Gate before the write, where refusing is still
 * free; file the entity_edits audit row after it, degraded to a warning
 * rather than a 500 over an edit that already landed.
 *
 * These paths sit beside the retriever read proxies (/api/events etc.), and
 * find-my-way gives a parametric PATCH route precedence over the proxy's
 * wildcard — the read side keeps proxying untouched.
 */

const ENTITIES: Record<string, string> = {
  events: "event",
  venues: "venue",
  artists: "artist",
};

/** What the pusher answers a PATCH with — the shared UpdateResult. */
interface UpdateResult {
  status: string;
  uid: string | null;
  changed?: Record<string, unknown>;
  warnings?: string[];
  message?: string;
}

/**
 * The org whose live claim carries this edit, for the audit row: the first
 * active claim on the entity held by an org the editor has a seat in. Several
 * orgs can hold claims on one entity; the editor's own is the one that
 * granted the right.
 */
async function orgHolding(
  db: SupabaseAdmin,
  entityType: string,
  uid: string,
  userId: string,
): Promise<string | null> {
  const seats = await db.select<{ org_id: string }>(
    "organization_members",
    `select=org_id&user_id=eq.${encodeURIComponent(userId)}`,
  );
  const mine = new Set(seats.map((seat) => seat.org_id));
  const claims = await db.select<{ org_id: string }>(
    "entity_ownership",
    `select=org_id&entity_type=eq.${entityType}` +
      `&entity_uid=eq.${encodeURIComponent(uid)}&status=eq.active`,
  );
  return claims.find((claim) => mine.has(claim.org_id))?.org_id ?? null;
}

export function registerEdits(app: FastifyInstance, config: GatewayConfig): void {
  const db = createSupabaseAdmin(config);
  const pro = { preHandler: requireRole("pro") };

  for (const [plural, entityType] of Object.entries(ENTITIES)) {
    app.patch(`/api/${plural}/:uid`, pro, async (request, reply) => {
      const user = request.user;
      if (!user) return reply.code(401).send({ error: "authentication required" });
      const { uid } = request.params as { uid: string };
      const body = (request.body ?? {}) as { fields?: unknown };
      const fields = body.fields;
      if (!fields || typeof fields !== "object" || Array.isArray(fields)) {
        return reply.code(400).send({ error: "body must carry a fields object" });
      }

      // The one authorization question, asked before the graph write. The
      // function takes the uid as a parameter and is granted to service_role
      // expressly for this caller — plain rpc(), never rpcAsUser (that flow
      // exists for functions that read auth.uid(), which this one does not).
      // Admin bypasses: the review queue's revert path must not depend on
      // holding a claim.
      if (user.role !== "admin") {
        let may: boolean;
        try {
          may = await db.rpc<boolean>("user_may_edit", {
            p_entity_type: entityType,
            p_entity_uid: uid,
            p_uid: user.id,
          });
        } catch (error) {
          request.log.error({ err: error }, "user_may_edit failed");
          return reply
            .code(503)
            .send({ error: "could not check edit rights — try again in a moment" });
        }
        if (!may) {
          return reply
            .code(403)
            .send({ error: `your organisation does not manage this ${entityType}` });
        }
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
        upstream = await fetch(
          `${config.pusherUrl}/${plural}/${encodeURIComponent(uid)}`,
          { method: "PATCH", headers, body: JSON.stringify({ fields }) },
        );
      } catch (error) {
        request.log.error({ err: error }, "edit upstream unreachable");
        return reply.code(502).send({ error: "could not apply that edit" });
      }

      const answer: unknown = await upstream.json().catch(() => null);
      // The pusher owns the verdict on the fields — its 404/409/422/503 pass
      // straight through rather than being reinterpreted here.
      if (!upstream.ok) return reply.code(upstream.status).send(answer ?? {});

      const result = answer as UpdateResult;
      const warnings = [...(result.warnings ?? [])];

      // The audit row, after the write and never fatal to it. entity_edits is
      // RLS-locked to the service role; `changes` carries the writer's own
      // old/new delta per field, which is what makes an admin revert possible.
      if (result.changed && Object.keys(result.changed).length) {
        try {
          const orgId =
            user.role === "admin"
              ? null
              : await orgHolding(db, entityType, uid, user.id);
          await db.insert("entity_edits", [
            {
              entity_type: entityType,
              entity_uid: uid,
              org_id: orgId,
              user_id: user.id,
              changes: result.changed,
            },
          ]);
        } catch (error) {
          request.log.error({ err: error }, "edit not audited");
          warnings.push("Edited, but the change was not recorded in the audit log.");
        }
      }

      return reply.send({ ...result, warnings });
    });
  }
}
