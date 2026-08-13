import { randomUUID } from "node:crypto";
import cors from "@fastify/cors";
import rateLimit from "@fastify/rate-limit";
import Fastify, { type FastifyInstance } from "fastify";
import { registerAuth } from "./auth.js";
import type { GatewayConfig } from "./config.js";
import { registerConversationLogging } from "./logging.js";
import { registerProxies } from "./proxy.js";
import "./types.js";

export async function buildServer(config: GatewayConfig): Promise<FastifyInstance> {
  const app = Fastify({
    logger: { level: config.logLevel },
    genReqId: () => randomUUID(),
    // SSE responses must not idle out mid-stream while the composer thinks
    connectionTimeout: 0,
    requestTimeout: 0,
  });

  await app.register(cors, {
    origin: config.corsAllowOrigins,
    methods: ["GET", "POST", "OPTIONS"],
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

  await app.register(rateLimit, {
    global: true,
    timeWindow: config.rateLimitWindowMs,
    max: (request) => (request.user ? config.rateLimitUserMax : config.rateLimitAnonMax),
    keyGenerator: (request) => request.user?.id ?? request.ip,
    allowList: (request) => request.url === "/healthz",
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
  const UPLOAD_ROUTES = [/^\/api\/transcribe(\/|$)/, /^\/api\/push\/(ingest|batch\/parse)(\/|$)/];
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

  app.get("/healthz", async () => ({ status: "ok", service: "gateway" }));

  registerProxies(app, config);
  registerConversationLogging(app, config);

  return app;
}
