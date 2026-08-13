import type { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import { createRemoteJWKSet, jwtVerify } from "jose";
import type { GatewayConfig } from "./config.js";
import type { AuthUser, UserRole } from "./types.js";

const ROLES: readonly UserRole[] = ["user", "pro", "admin"];

/**
 * Verifies Supabase JWTs against the project JWKS. No token = anonymous
 * (request.user stays null, D7); a token that is present but invalid is a
 * hard 401 everywhere — never silently downgraded to anonymous.
 *
 * The role comes from the `user_role` claim embedded by the custom access
 * token hook (supabase/migrations); the standard Supabase `role` claim is the
 * Postgres role ("authenticated") and is deliberately ignored.
 */
export function registerAuth(app: FastifyInstance, config: GatewayConfig): void {
  const jwks = createRemoteJWKSet(new URL(config.jwksUrl));

  app.decorateRequest("user", null);

  app.addHook("onRequest", async (request: FastifyRequest, reply: FastifyReply) => {
    const header = request.headers.authorization;
    if (!header) return;

    const [scheme, token] = header.split(" ");
    if (scheme?.toLowerCase() !== "bearer" || !token) {
      return reply.code(401).send({ error: "malformed authorization header" });
    }

    try {
      const { payload } = await jwtVerify(token, jwks, {
        issuer: config.jwtIssuer,
        audience: config.jwtAudience,
        algorithms: ["ES256", "RS256"],
      });
      if (typeof payload.sub !== "string" || payload.sub.length === 0) {
        return reply.code(401).send({ error: "token has no subject" });
      }
      const claimedRole = payload["user_role"];
      const role: UserRole = ROLES.includes(claimedRole as UserRole)
        ? (claimedRole as UserRole)
        : "user";
      request.user = { id: payload.sub, role } satisfies AuthUser;
    } catch {
      return reply.code(401).send({ error: "invalid or expired token" });
    }
  });
}

/** 401 for anonymous, 403 below `minimum`. Role order: user < pro < admin. */
export function requireRole(minimum: UserRole) {
  return async (request: FastifyRequest, reply: FastifyReply) => {
    if (!request.user) {
      return reply.code(401).send({ error: "authentication required" });
    }
    if (ROLES.indexOf(request.user.role) < ROLES.indexOf(minimum)) {
      return reply.code(403).send({ error: `${minimum} role required` });
    }
  };
}
