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

  // /api/push/* → pusher /* — pro and admin only
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
      prefix: "/api/push",
      rewritePrefix: "",
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
