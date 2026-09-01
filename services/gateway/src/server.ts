import { randomUUID } from "node:crypto";
import cors from "@fastify/cors";
import rateLimit from "@fastify/rate-limit";
import Fastify, { type FastifyInstance } from "fastify";
import { Redis } from "ioredis";
import { registerAuth } from "./auth.js";
import type { GatewayConfig } from "./config.js";
import { registerFeedback } from "./feedback.js";
import { registerOrgs } from "./orgs.js";
import { registerConversationLogging } from "./logging.js";
import { registerProxies } from "./proxy.js";
import "./types.js";

// The kubelet cannot authenticate, so these are exempt from the rate limit. They
// are also the only routes that must answer while a dependency is down.
const PROBE_PATHS = new Set(["/healthz", "/readyz"]);

export async function buildServer(config: GatewayConfig): Promise<FastifyInstance> {
  const app = Fastify({
    logger: { level: config.logLevel },
    genReqId: () => randomUUID(),
    // SSE responses must not idle out mid-stream while the composer thinks
    connectionTimeout: 0,
    requestTimeout: 0,
    // One hop — Traefik. Without this, `request.ip` is the ingress pod's address
    // and every anonymous user on earth shares a single rate-limit bucket. Not
    // `true`: that would trust a client-supplied X-Forwarded-For chain of any
    // length, which is a rate-limit bypass. Requires the ingress to preserve the
    // client IP (externalTrafficPolicy: Local).
    trustProxy: 1,
  });

  await app.register(cors, {
    origin: config.corsAllowOrigins,
    methods: ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allowedHeaders: ["content-type", "authorization"],
    exposedHeaders: [
      "x-request-id",
      "x-login-upsell",
      "x-ratelimit-limit",
      "x-ratelimit-remaining",
      "x-ratelimit-reset",
    ],
  });

  registerAuth(app, config);

  // Quota has to be one bucket per identity across every replica, not per
  // process — with the default in-memory store, N replicas silently grant N×
  // everyone's quota. Redis is the only distributed store this plugin supports.
  // Unset REDIS_URL keeps the in-memory store, so local runs and the tests need
  // no new infrastructure.
  const redis = config.redisUrl
    ? new Redis(config.redisUrl, {
        connectTimeout: 500,
        maxRetriesPerRequest: 1,
        // Fail loudly instead of queueing commands against a dead Redis.
        enableOfflineQueue: false,
      })
    : undefined;
  if (redis) {
    redis.on("error", (error: Error) => app.log.error({ err: error }, "redis"));
    app.addHook("onClose", async () => {
      await redis.quit().catch(() => redis.disconnect());
    });
  }

  await app.register(rateLimit, {
    global: true,
    timeWindow: config.rateLimitWindowMs,
    max: (request) => {
      if (!request.user) return config.rateLimitAnonMax;
      if (request.user.role === "admin") return config.rateLimitAdminMax;
      if (request.user.role === "pro") return config.rateLimitProMax;
      return config.rateLimitUserMax;
    },
    keyGenerator: (request) => request.user?.id ?? request.ip,
    allowList: (request) => PROBE_PATHS.has(request.url),
    redis,
    nameSpace: "rl:",
    // A Redis outage must not take the product down. Losing quota enforcement
    // for the duration is the cheaper failure — the upstream APIs are still
    // protected by UPLOAD_MAX_BYTES and by auth on the write routes.
    skipOnError: true,
    errorResponseBuilder: (request, context) => ({
      statusCode: 429,
      error: "Too Many Requests",
      message: request.user
        ? `rate limit exceeded, retry in ${context.after}`
        : `anonymous rate limit exceeded, retry in ${context.after} — sign in for a higher quota`,
    }),
  });

  // Upload routes are proxied as raw streams, which means Fastify's body limit
  // never sees them. Reject oversized bodies on the declared length before any
  // of it reaches Whisper or the vision model.
  const UPLOAD_ROUTES = [/^\/api\/transcribe(\/|$)/, /^\/api\/push\/ingest(\/|$)/];
  app.addHook("onRequest", async (request, reply) => {
    if (request.method !== "POST") return;
    if (!UPLOAD_ROUTES.some((route) => route.test(request.url))) return;
    const declared = Number(request.headers["content-length"] ?? 0);
    if (declared > config.uploadMaxBytes) {
      return reply
        .code(413)
        .send({ error: `upload exceeds ${Math.floor(config.uploadMaxBytes / 1024)} kB` });
    }
  });

  app.addHook("onSend", async (request, reply) => {
    reply.header("x-request-id", request.id);
    if (!request.user && request.url.startsWith("/api/")) {
      reply.header("x-login-upsell", "sign in for a higher quota");
    }
  });

  // Liveness: is the process wedged? Checks nothing on purpose — a liveness
  // probe that touches a dependency turns someone else's outage into a restart
  // loop. Same split the Python services get from laiive_shared.health.
  app.get("/healthz", async () => ({ status: "ok", service: "gateway" }));

  // Readiness: should this replica take traffic? Redis is the only dependency
  // the gateway holds itself; auth uses a remote JWKS it caches, and the
  // services have their own probes.
  app.get("/readyz", async (_request, reply) => {
    if (!redis) return { status: "ready", service: "gateway" };
    try {
      await redis.ping();
      return { status: "ready", service: "gateway" };
    } catch (error) {
      return reply
        .code(503)
        .send({ status: "not_ready", service: "gateway", reason: String(error) });
    }
  });

  registerFeedback(app, config);
  registerOrgs(app, config);
  registerProxies(app, config);
  registerConversationLogging(app, config);

  return app;
}
