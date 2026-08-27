import type { FastifyInstance } from "fastify";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { buildServer } from "../src/server.js";
import { startSupabaseStub, startUpstreamStub, testConfig } from "./helpers.js";

let supabase: Awaited<ReturnType<typeof startSupabaseStub>>;
let retriever: Awaited<ReturnType<typeof startUpstreamStub>>;
let app: FastifyInstance;

beforeAll(async () => {
  supabase = await startSupabaseStub();
  retriever = await startUpstreamStub();
  app = await buildServer(
    testConfig({ supabaseUrl: supabase.url, retrieverUrl: retriever.url }),
  );
  await app.ready();
});

afterAll(async () => {
  await app.close();
  await Promise.all([supabase.close(), retriever.close()]);
});

describe("POST /api/chat/feedback", () => {
  it("inserts a thumbs-down anonymously — the static route wins over the chat proxy wildcard", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/api/chat/feedback",
      payload: { request_id: "req-1" },
    });
    expect(res.statusCode).toBe(204);
    expect(supabase.feedbackInserts).toContainEqual({
      request_id: "req-1",
      user_id: null,
      reason: null,
      rating: "down",
    });
    // Nothing was proxied to the retriever.
    expect(retriever.seen.filter((r) => r.url.includes("feedback"))).toHaveLength(0);
  });

  it("stamps the signed-in user's id and carries the reason", async () => {
    const token = await supabase.signToken({ sub: "d3b07384-d9a0-4c9a-8f4e-000000000001" });
    const res = await app.inject({
      method: "POST",
      url: "/api/chat/feedback",
      headers: { authorization: `Bearer ${token}` },
      payload: { request_id: "req-2", reason: "wrong city" },
    });
    expect(res.statusCode).toBe(204);
    expect(supabase.feedbackInserts).toContainEqual({
      request_id: "req-2",
      user_id: "d3b07384-d9a0-4c9a-8f4e-000000000001",
      reason: "wrong city",
      rating: "down",
    });
  });

  it("stores a thumbs-up when the client says so", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/api/chat/feedback",
      payload: { request_id: "req-up", rating: "up" },
    });
    expect(res.statusCode).toBe(204);
    expect(supabase.feedbackInserts).toContainEqual({
      request_id: "req-up",
      user_id: null,
      reason: null,
      rating: "up",
    });
  });

  it("rejects a rating that is neither up nor down", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/api/chat/feedback",
      payload: { request_id: "req-bad", rating: "sideways" },
    });
    expect(res.statusCode).toBe(400);
    expect(
      supabase.feedbackInserts.filter(
        (r) => (r as { request_id: string }).request_id === "req-bad",
      ),
    ).toHaveLength(0);
  });

  it("rejects a missing request_id and an oversized reason", async () => {
    const missing = await app.inject({ method: "POST", url: "/api/chat/feedback", payload: {} });
    expect(missing.statusCode).toBe(400);

    const oversized = await app.inject({
      method: "POST",
      url: "/api/chat/feedback",
      payload: { request_id: "req-3", reason: "x".repeat(2001) },
    });
    expect(oversized.statusCode).toBe(400);
    expect(supabase.feedbackInserts.filter((r) => (r as { request_id: string }).request_id === "req-3")).toHaveLength(0);
  });
});
