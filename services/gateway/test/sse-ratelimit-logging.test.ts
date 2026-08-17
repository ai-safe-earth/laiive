import type { FastifyInstance } from "fastify";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { buildServer } from "../src/server.js";
import { startSupabaseStub, startUpstreamStub, testConfig } from "./helpers.js";

let supabase: Awaited<ReturnType<typeof startSupabaseStub>>;
let retriever: Awaited<ReturnType<typeof startUpstreamStub>>;
let app: FastifyInstance | null = null;

beforeEach(async () => {
  supabase = await startSupabaseStub();
  retriever = await startUpstreamStub();
});

afterEach(async () => {
  if (app) await app.close();
  app = null;
  await Promise.all([supabase.close(), retriever.close()]);
});

describe("sse pass-through", () => {
  it("streams chunks as they are produced, unbuffered", async () => {
    app = await buildServer(
      testConfig({ supabaseUrl: supabase.url, retrieverUrl: retriever.url }),
    );
    await app.listen({ host: "127.0.0.1", port: 0 });
    const port = (app.server.address() as { port: number }).port;

    const res = await fetch(`http://127.0.0.1:${port}/api/chat/stream`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message: "hi" }),
    });
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/event-stream");

    const chunks: string[] = [];
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(decoder.decode(value, { stream: true }));
    }
    // upstream writes 3 frames 40ms apart — a buffering proxy would deliver 1 chunk
    expect(chunks.length).toBeGreaterThanOrEqual(2);
    expect(chunks.join("")).toBe(
      'data: {"delta": "hello"}\n\ndata: {"delta": " world"}\n\ndata: [DONE]\n\n',
    );
  });
});

describe("rate limits", () => {
  it("caps anonymous users per IP with a login upsell, authed users by sub", async () => {
    app = await buildServer(
      testConfig({
        supabaseUrl: supabase.url,
        retrieverUrl: retriever.url,
        rateLimitAnonMax: 2,
        rateLimitUserMax: 4,
      }),
    );
    await app.ready();

    for (let i = 0; i < 2; i++) {
      const res = await app.inject({ method: "POST", url: "/api/chat", payload: {} });
      expect(res.statusCode).toBe(200);
      expect(String(res.headers["x-ratelimit-limit"])).toBe("2");
    }
    const blocked = await app.inject({ method: "POST", url: "/api/chat", payload: {} });
    expect(blocked.statusCode).toBe(429);
    expect(JSON.parse(blocked.body).message).toContain("sign in");

    // same IP, but authenticated: keyed by sub with the higher cap
    const token = await supabase.signToken({ sub: "user-limits" });
    for (let i = 0; i < 4; i++) {
      const res = await app.inject({
        method: "POST",
        url: "/api/chat",
        headers: { authorization: `Bearer ${token}` },
        payload: {},
      });
      expect(res.statusCode).toBe(200);
    }
    const authedBlocked = await app.inject({
      method: "POST",
      url: "/api/chat",
      headers: { authorization: `Bearer ${token}` },
      payload: {},
    });
    expect(authedBlocked.statusCode).toBe(429);
    expect(JSON.parse(authedBlocked.body).message).not.toContain("sign in");

    // healthz is never rate limited
    const health = await app.inject({ method: "GET", url: "/healthz" });
    expect(health.statusCode).toBe(200);
  });

  it("buckets anonymous users by the forwarded client IP, not the proxy's", async () => {
    // Behind an ingress every request arrives from the same proxy address. Without
    // trustProxy the whole internet would share one anonymous bucket.
    app = await buildServer(
      testConfig({
        supabaseUrl: supabase.url,
        retrieverUrl: retriever.url,
        rateLimitAnonMax: 1,
      }),
    );
    await app.ready();

    const first = await app.inject({
      method: "POST",
      url: "/api/chat",
      headers: { "x-forwarded-for": "203.0.113.7" },
      payload: {},
    });
    expect(first.statusCode).toBe(200);

    const sameClient = await app.inject({
      method: "POST",
      url: "/api/chat",
      headers: { "x-forwarded-for": "203.0.113.7" },
      payload: {},
    });
    expect(sameClient.statusCode).toBe(429);

    const otherClient = await app.inject({
      method: "POST",
      url: "/api/chat",
      headers: { "x-forwarded-for": "203.0.113.8" },
      payload: {},
    });
    expect(otherClient.statusCode).toBe(200);
  });

  it("builds with no REDIS_URL and keeps the in-memory store", async () => {
    // The Redis store is what makes the quota correct across replicas, but a
    // missing REDIS_URL must never be a startup failure — that is the local and
    // single-process path.
    app = await buildServer(
      testConfig({ supabaseUrl: supabase.url, retrieverUrl: retriever.url, redisUrl: "" }),
    );
    await app.ready();

    const ready = await app.inject({ method: "GET", url: "/readyz" });
    expect(ready.statusCode).toBe(200);
    expect(JSON.parse(ready.body).status).toBe("ready");
  });
});

describe("conversation logging", () => {
  it("fires an insert per chat request with payload, user and status", async () => {
    app = await buildServer(
      testConfig({
        supabaseUrl: supabase.url,
        retrieverUrl: retriever.url,
        conversationLogging: true,
      }),
    );
    await app.ready();

    const token = await supabase.signToken({ sub: "logged-user", role: "pro" });
    const res = await app.inject({
      method: "POST",
      url: "/api/chat",
      headers: { authorization: `Bearer ${token}` },
      payload: { message: "find jazz tonight" },
    });
    expect(res.statusCode).toBe(200);

    await expect
      .poll(() => supabase.logInserts.length, { timeout: 3000 })
      .toBeGreaterThanOrEqual(1);
    const record = supabase.logInserts[0] as Record<string, unknown>;
    expect(record.user_id).toBe("logged-user");
    expect(record.user_role).toBe("pro");
    expect(record.route).toBe("/api/chat");
    expect(record.status).toBe(200);
    expect(record.payload).toEqual({ message: "find jazz tonight" });
    expect(record.request_id).toBe(res.headers["x-request-id"]);
  });

  it("does not log GET or non-conversation routes", async () => {
    app = await buildServer(
      testConfig({
        supabaseUrl: supabase.url,
        retrieverUrl: retriever.url,
        conversationLogging: true,
      }),
    );
    await app.ready();

    await app.inject({ method: "GET", url: "/healthz" });
    await new Promise((resolve) => setTimeout(resolve, 200));
    expect(supabase.logInserts).toHaveLength(0);
  });
});
