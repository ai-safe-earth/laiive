import httpProxy, { type FastifyHttpProxyOptions } from "@fastify/http-proxy";
import type { FastifyInstance } from "fastify";
import type { GatewayConfig } from "./config.js";
import { requireRole } from "./auth.js";

/**
 * The services trust identity headers because they are unreachable except
 * through the gateway — and, when INTERNAL_API_KEY is set, because they check.
 * Client-sent copies of everything the gateway asserts are dropped first;
 * `x-internal-key` belongs in that strip-list precisely because it is what
 * protects the rest.
 */
const replyOptionsFor = (
  config: GatewayConfig,
): NonNullable<FastifyHttpProxyOptions["replyOptions"]> => ({
  rewriteRequestHeaders: (request, headers) => {
    const out = { ...headers };
    delete out["x-user-id"];
    delete out["x-user-role"];
    delete out["x-request-id"];
    delete out["x-internal-key"];
    delete out.authorization;
    out["x-request-id"] = String(request.id);
    if (config.internalApiKey) out["x-internal-key"] = config.internalApiKey;
    if (request.user) {
      out["x-user-id"] = request.user.id;
      out["x-user-role"] = request.user.role;
    }
    return out;
  },
});

export function registerProxies(app: FastifyInstance, config: GatewayConfig): void {
  const replyOptions = replyOptionsFor(config);

  // Chat proxies parse the JSON body (proxyPayloads: false) so conversation
  // logging can capture it; everything else streams bodies through untouched
  // (audio/file uploads must not be buffered or parsed here).

  // /api/chat/* → retriever /chat/* — anonymous allowed (D7)
  app.register(httpProxy, {
    upstream: config.retrieverUrl,
    prefix: "/api/chat",
    rewritePrefix: "/chat",
    proxyPayloads: false,
    replyOptions,
  });

  // /api/transcribe → retriever /transcribe — anonymous allowed: voice input is
  // public (D7). Multipart audio streams through unparsed, and the anonymous
  // per-IP quota is what bounds the Whisper spend (the service also caps size).
  app.register(httpProxy, {
    upstream: config.retrieverUrl,
    prefix: "/api/transcribe",
    rewritePrefix: "/transcribe",
    replyOptions,
  });

  // /api/events → retriever /events — any signed-in account, no role floor.
  //
  // Not folded into /api/chat: that prefix is anonymous by decision (D7) and
  // scoped to a chat turn, and this is a by-uid lookup for the caller's own
  // saved list. Saving needs an account, so the rule belongs here rather than
  // only in a client we ship. requireRole("user") is exactly "present a valid
  // token" — user is the floor of the role order, so it 401s anonymous and
  // refuses nobody who is signed in.
  app.register(async (scope) => {
    scope.addHook("preHandler", requireRole("user"));
    scope.register(httpProxy, {
      upstream: config.retrieverUrl,
      prefix: "/api/events",
      rewritePrefix: "/events",
      replyOptions,
    });
  });

  // /api/venues, /api/artists → retriever lookups — pro only. The consumers
  // are the pro event form and the coming org screen; the venue base stays
  // off the anonymous surface.
  app.register(async (scope) => {
    scope.addHook("preHandler", requireRole("pro"));
    scope.register(httpProxy, {
      upstream: config.retrieverUrl,
      prefix: "/api/venues",
      rewritePrefix: "/venues",
      replyOptions,
    });
    scope.register(httpProxy, {
      upstream: config.retrieverUrl,
      prefix: "/api/artists",
      rewritePrefix: "/artists",
      replyOptions,
    });
  });

  // /api/push/* → pusher — pro and admin only, and EXPLICIT routes rather than
  // a catch-all. The old `prefix: "/api/push", rewritePrefix: ""` exposed every
  // pusher route, present and future, behind one pro gate — which turns into a
  // hole the moment the pusher grows endpoints the gateway must authorize
  // per-entity (the ownership edit routes). A new pusher endpoint now has to be
  // named here to exist at all.
  app.register(async (scope) => {
    scope.addHook("preHandler", requireRole("pro"));
    scope.register(httpProxy, {
      upstream: config.pusherUrl,
      prefix: "/api/push/chat",
      rewritePrefix: "/chat",
      proxyPayloads: false,
      replyOptions,
    });
    scope.register(httpProxy, {
      upstream: config.pusherUrl,
      prefix: "/api/push/validate-event",
      rewritePrefix: "/validate-event",
      replyOptions,
    });
    scope.register(httpProxy, {
      upstream: config.pusherUrl,
      prefix: "/api/push/ingest",
      rewritePrefix: "/ingest",
      replyOptions,
    });
    // Named because scripts/e2e-live.mjs probes it for readiness and for the
    // role-gate checks — the catch-all used to expose it by accident, this
    // keeps it by decision.
    scope.register(httpProxy, {
      upstream: config.pusherUrl,
      prefix: "/api/push/health",
      rewritePrefix: "/health",
      replyOptions,
    });
  });

  // /api/admin/search/* → search service — admin only; 503 until Phase 5 deploys it
  app.register(async (scope) => {
    scope.addHook("preHandler", requireRole("admin"));
    if (config.searchEnabled) {
      scope.register(httpProxy, {
        upstream: config.searchUrl,
        prefix: "/api/admin/search",
        rewritePrefix: "",
        replyOptions,
      });
    } else {
      scope.all("/api/admin/search/*", async (_request, reply) => {
        return reply.code(503).send({ error: "SEARCH service not deployed (Phase 5)" });
      });
    }
  });
}
