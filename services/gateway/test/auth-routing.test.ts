import type { FastifyInstance } from "fastify";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { buildServer } from "../src/server.js";
import { startSupabaseStub, startUpstreamStub, testConfig, type SeenRequest } from "./helpers.js";

let supabase: Awaited<ReturnType<typeof startSupabaseStub>>;
let retriever: Awaited<ReturnType<typeof startUpstreamStub>>;
let pusher: Awaited<ReturnType<typeof startUpstreamStub>>;
let app: FastifyInstance;

beforeAll(async () => {
  supabase = await startSupabaseStub();
  retriever = await startUpstreamStub();
  pusher = await startUpstreamStub();
  app = await buildServer(
    testConfig({
      supabaseUrl: supabase.url,
      retrieverUrl: retriever.url,
      pusherUrl: pusher.url,
    }),
  );
  await app.ready();
});

afterAll(async () => {
  await app.close();
  await Promise.all([supabase.close(), retriever.close(), pusher.close()]);
});

describe("auth", () => {
  it("lets anonymous users chat (D7) and marks the response with an upsell header", async () => {
    const res = await app.inject({ method: "POST", url: "/api/chat", payload: { message: "hi" } });
    expect(res.statusCode).toBe(200);
    expect(res.headers["x-login-upsell"]).toBeDefined();
    expect(res.headers["x-request-id"]).toBeDefined();
  });

  it("rejects a malformed authorization header", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/api/chat",
      headers: { authorization: "Basic abc" },
      payload: {},
    });
    expect(res.statusCode).toBe(401);
  });

  it("rejects an invalid token even on anonymous-allowed routes", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/api/chat",
      headers: { authorization: "Bearer not-a-jwt" },
      payload: {},
    });
    expect(res.statusCode).toBe(401);
  });

  it("rejects an expired token", async () => {
    const token = await supabase.signToken({ expiresIn: "-1h" });
    const res = await app.inject({
      method: "POST",
      url: "/api/chat",
      headers: { authorization: `Bearer ${token}` },
      payload: {},
    });
    expect(res.statusCode).toBe(401);
  });

  it("requires auth for /api/push/*", async () => {
    const res = await app.inject({ method: "POST", url: "/api/push/validate-event", payload: {} });
    expect(res.statusCode).toBe(401);
  });

  it("rejects plain users on /api/push/* with 403", async () => {
    const token = await supabase.signToken({ role: "user" });
    const res = await app.inject({
      method: "POST",
      url: "/api/push/validate-event",
      headers: { authorization: `Bearer ${token}` },
      payload: {},
    });
    expect(res.statusCode).toBe(403);
  });

  it("treats an unknown role claim as plain user", async () => {
    const token = await supabase.signToken({ role: "superadmin" });
    const res = await app.inject({
      method: "POST",
      url: "/api/push/validate-event",
      headers: { authorization: `Bearer ${token}` },
      payload: {},
    });
    expect(res.statusCode).toBe(403);
  });

  it("lets pros through to the pusher", async () => {
    const token = await supabase.signToken({ sub: "pro-7", role: "pro" });
    const res = await app.inject({
      method: "POST",
      url: "/api/push/validate-event",
      headers: { authorization: `Bearer ${token}` },
      payload: { draft: {} },
    });
    expect(res.statusCode).toBe(200);
    const upstream = JSON.parse(res.body) as SeenRequest;
    expect(upstream.url).toBe("/validate-event");
    expect(upstream.headers["x-user-id"]).toBe("pro-7");
    expect(upstream.headers["x-user-role"]).toBe("pro");
  });

  it("refuses pusher routes the gateway does not name (no catch-all)", async () => {
    // The old /api/push catch-all exposed every pusher route, present and
    // future, behind one pro gate. Explicit routes mean a new pusher endpoint
    // has to be named in proxy.ts to exist at all — pinned here so a future
    // "convenient" catch-all fails this test.
    const token = await supabase.signToken({ role: "pro" });
    const res = await app.inject({
      method: "PATCH",
      url: "/api/push/venues/v1",
      headers: { authorization: `Bearer ${token}` },
      payload: {},
    });
    expect(res.statusCode).toBe(404);
  });

  it("still answers the health probe the live e2e script relies on", async () => {
    const token = await supabase.signToken({ role: "pro" });
    const res = await app.inject({
      method: "GET",
      url: "/api/push/health",
      headers: { authorization: `Bearer ${token}` },
    });
    expect(res.statusCode).toBe(200);
    expect((JSON.parse(res.body) as SeenRequest).url).toBe("/health");
  });

  it("keeps anonymous and plain users away from the entity lookups", async () => {
    const anon = await app.inject({ method: "GET", url: "/api/venues?q=razz" });
    expect(anon.statusCode).toBe(401);
    const token = await supabase.signToken({ role: "user" });
    const user = await app.inject({
      method: "GET",
      url: "/api/venues?q=razz",
      headers: { authorization: `Bearer ${token}` },
    });
    expect(user.statusCode).toBe(403);
  });

  it("routes a pro's venue and artist lookups to the retriever, query intact", async () => {
    const token = await supabase.signToken({ role: "pro" });
    const venues = await app.inject({
      method: "GET",
      url: "/api/venues?q=razz&city=Barcelona",
      headers: { authorization: `Bearer ${token}` },
    });
    expect(venues.statusCode).toBe(200);
    expect((JSON.parse(venues.body) as SeenRequest).url).toBe("/venues?q=razz&city=Barcelona");

    const artists = await app.inject({
      method: "GET",
      url: "/api/artists?q=ana",
      headers: { authorization: `Bearer ${token}` },
    });
    expect(artists.statusCode).toBe(200);
    expect((JSON.parse(artists.body) as SeenRequest).url).toBe("/artists?q=ana");
  });

  it("keeps admins out of nothing and pros out of admin search", async () => {
    const pro = await supabase.signToken({ role: "pro" });
    const admin = await supabase.signToken({ role: "admin" });
    const proRes = await app.inject({
      method: "POST",
      url: "/api/admin/search/run",
      headers: { authorization: `Bearer ${pro}` },
      payload: {},
    });
    expect(proRes.statusCode).toBe(403);
    const adminRes = await app.inject({
      method: "POST",
      url: "/api/admin/search/run",
      headers: { authorization: `Bearer ${admin}` },
      payload: {},
    });
    expect(adminRes.statusCode).toBe(503); // search service not deployed until Phase 5
  });
});

describe("uploads", () => {
  it("routes anonymous voice input to the retriever (D7)", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/api/transcribe",
      headers: { "content-type": "audio/webm" },
      payload: Buffer.from("fake-audio"),
    });
    expect(res.statusCode).toBe(200);
    const upstream = JSON.parse(res.body) as SeenRequest;
    expect(upstream.url).toBe("/transcribe");
    // Anonymous: no identity headers are injected, but the upsell still fires.
    expect(upstream.headers["x-user-id"]).toBeUndefined();
    expect(res.headers["x-login-upsell"]).toBeDefined();
  });

  it("routes pro ingestion to the pusher", async () => {
    const token = await supabase.signToken({ sub: "pro-9", role: "pro" });
    const res = await app.inject({
      method: "POST",
      url: "/api/push/ingest",
      headers: { authorization: `Bearer ${token}`, "content-type": "application/pdf" },
      payload: Buffer.from("%PDF-1.4"),
    });
    expect(res.statusCode).toBe(200);
    const upstream = JSON.parse(res.body) as SeenRequest;
    expect(upstream.url).toBe("/ingest");
    expect(upstream.headers["x-user-id"]).toBe("pro-9");
  });

  it("refuses an oversized upload before it reaches the metered API", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/api/transcribe",
      headers: { "content-type": "audio/webm" },
      payload: Buffer.alloc(8192, 1), // testConfig caps uploads at 4 kB
    });
    expect(res.statusCode).toBe(413);
  });
});

describe("identity headers", () => {
  it("strips client-sent identity headers and injects verified ones", async () => {
    const token = await supabase.signToken({ sub: "user-9", role: "user" });
    const res = await app.inject({
      method: "POST",
      url: "/api/chat",
      headers: {
        authorization: `Bearer ${token}`,
        "x-user-id": "spoofed-admin",
        "x-user-role": "admin",
        "x-request-id": "spoofed-request",
      },
      payload: { message: "hi" },
    });
    expect(res.statusCode).toBe(200);
    const upstream = JSON.parse(res.body) as SeenRequest;
    expect(upstream.url).toBe("/chat");
    expect(upstream.headers["x-user-id"]).toBe("user-9");
    expect(upstream.headers["x-user-role"]).toBe("user");
    expect(upstream.headers["x-request-id"]).not.toBe("spoofed-request");
    expect(upstream.headers.authorization).toBeUndefined();
  });

  it("forwards no identity headers for anonymous requests", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/api/chat",
      headers: { "x-user-id": "spoofed" },
      payload: { message: "hi" },
    });
    expect(res.statusCode).toBe(200);
    const upstream = JSON.parse(res.body) as SeenRequest;
    expect(upstream.headers["x-user-id"]).toBeUndefined();
    expect(upstream.headers["x-request-id"]).toBeDefined();
  });

  it("injects the internal key and refuses to forward a client's own", async () => {
    // The services reject anything without this header, so a client able to set
    // it would be able to reach them directly — it must be stripped like the
    // identity headers it protects.
    // A local instance: the shared `app` is built once in beforeAll and every
    // other test depends on its config.
    const keyed = await buildServer(
      testConfig({
        supabaseUrl: supabase.url,
        retrieverUrl: retriever.url,
        internalApiKey: "real-internal-key", // pragma: allowlist secret
      }),
    );
    try {
      const res = await keyed.inject({
        method: "POST",
        url: "/api/chat",
        headers: { "x-internal-key": "client-supplied" },
        payload: { message: "hi" },
      });
      expect(res.statusCode).toBe(200);
      const upstream = JSON.parse(res.body) as SeenRequest;
      expect(upstream.headers["x-internal-key"]).toBe("real-internal-key");
    } finally {
      await keyed.close();
    }
  });

  it("sends no internal key when none is configured", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/api/chat",
      headers: { "x-internal-key": "client-supplied" },
      payload: { message: "hi" },
    });
    expect(res.statusCode).toBe(200);
    const upstream = JSON.parse(res.body) as SeenRequest;
    expect(upstream.headers["x-internal-key"]).toBeUndefined();
  });
});

describe("the by-uid event lookup", () => {
  it("refuses an anonymous caller", async () => {
    // Saving needs an account, so the rule lives here and not only in a
    // client we ship.
    const res = await app.inject({ method: "GET", url: "/api/events?uids=e1" });
    expect(res.statusCode).toBe(401);
  });

  it("lets any signed-in account through, query string intact", async () => {
    const token = await supabase.signToken({ sub: "user-4", role: "user" });
    const res = await app.inject({
      method: "GET",
      url: "/api/events?uids=e1,e2",
      headers: { authorization: `Bearer ${token}` },
    });
    expect(res.statusCode).toBe(200);
    const upstream = JSON.parse(res.body) as SeenRequest;
    // The rewrite drops the prefix and nothing else — losing the query here
    // would look like "the graph has no saved events".
    expect(upstream.url).toBe("/events?uids=e1,e2");
    expect(upstream.headers["x-user-id"]).toBe("user-4");
  });
});

describe("cors", () => {
  it("allows the configured origin and refuses others", async () => {
    const ok = await app.inject({
      method: "OPTIONS",
      url: "/api/chat",
      headers: {
        origin: "http://localhost:8081",
        "access-control-request-method": "POST",
      },
    });
    expect(ok.headers["access-control-allow-origin"]).toBe("http://localhost:8081");

    const bad = await app.inject({
      method: "OPTIONS",
      url: "/api/chat",
      headers: {
        origin: "https://evil.example",
        "access-control-request-method": "POST",
      },
    });
    expect(bad.headers["access-control-allow-origin"]).toBeUndefined();
  });
});
