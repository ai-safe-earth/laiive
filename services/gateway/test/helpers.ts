import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";
import { exportJWK, generateKeyPair, SignJWT } from "jose";
import type { GatewayConfig } from "../src/config.js";

function listen(server: Server): Promise<number> {
  return new Promise((resolve, reject) => {
    server.listen(0, "127.0.0.1", () => resolve((server.address() as AddressInfo).port));
    server.on("error", reject);
  });
}

function close(server: Server): Promise<void> {
  return new Promise((resolve) => server.close(() => resolve()));
}

/**
 * Stands in for the Supabase project: serves the JWKS, signs tokens with the
 * matching private key, and records inserts into /rest/v1/conversation_logs.
 */
export async function startSupabaseStub() {
  const { publicKey, privateKey } = await generateKeyPair("ES256");
  const jwk = { ...(await exportJWK(publicKey)), kid: "test-key", alg: "ES256", use: "sig" };
  const logInserts: unknown[] = [];
  const feedbackInserts: unknown[] = [];
  // Two tables the orgs routes read and write. Seeded by the test, mutated by
  // the route under test — enough of PostgREST to make 409-on-duplicate and
  // the withdraw-is-a-revoke path real assertions rather than mock theatre.
  const members: Record<string, unknown>[] = [];
  const ownership: Record<string, unknown>[] = [];
  const promoterProfiles: Record<string, unknown>[] = [];
  // Every create_organization call, and what it was asked as. The route has to
  // send the *user's* token, not the service key, or auth.uid() is null in the
  // function and it refuses - so the test needs to see which was used.
  const rpcCalls: { fn: string; args: unknown; authorization: string }[] = [];

  /** `col=eq.value` pairs out of a PostgREST query string. */
  const filtersOf = (url: string): Record<string, string> => {
    const out: Record<string, string> = {};
    for (const [key, value] of new URL(url, "http://x").searchParams) {
      if (key !== "select" && value.startsWith("eq.")) out[key] = value.slice(3);
    }
    return out;
  };
  const matches = (row: Record<string, unknown>, f: Record<string, string>) =>
    Object.entries(f).every(([key, value]) => String(row[key]) === value);
  const json = (res: ServerResponse, status: number, body: unknown) => {
    res.statusCode = status;
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify(body));
  };
  const readBody = (req: IncomingMessage): Promise<string> =>
    new Promise((resolve) => {
      const chunks: Buffer[] = [];
      req.on("data", (chunk: Buffer) => chunks.push(chunk));
      req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    });

  const server = createServer((req: IncomingMessage, res: ServerResponse) => {
    if (req.url === "/auth/v1/.well-known/jwks.json") {
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ keys: [jwk] }));
      return;
    }
    if (
      (req.url === "/rest/v1/conversation_logs" || req.url === "/rest/v1/turn_feedback") &&
      req.method === "POST"
    ) {
      const sink = req.url === "/rest/v1/turn_feedback" ? feedbackInserts : logInserts;
      const chunks: Buffer[] = [];
      req.on("data", (chunk: Buffer) => chunks.push(chunk));
      req.on("end", () => {
        sink.push(JSON.parse(Buffer.concat(chunks).toString("utf8")));
        res.statusCode = 201;
        res.end();
      });
      return;
    }
    if (req.url?.startsWith("/rest/v1/promoter_profiles") && req.method === "GET") {
      const f = filtersOf(req.url);
      json(res, 200, promoterProfiles.filter((row) => matches(row, f)));
      return;
    }
    if (req.url?.startsWith("/rest/v1/rpc/") && req.method === "POST") {
      const fn = req.url.slice("/rest/v1/rpc/".length);
      void readBody(req).then((raw) => {
        rpcCalls.push({
          fn,
          args: JSON.parse(raw),
          authorization: String(req.headers.authorization ?? ""),
        });
        const orgId = `org-${rpcCalls.length}`;
        members.push({ org_id: orgId, user_id: "bootstrapped", role: "owner" });
        json(res, 200, orgId);
      });
      return;
    }
    if (req.url?.startsWith("/rest/v1/organization_members") && req.method === "GET") {
      const f = filtersOf(req.url);
      json(res, 200, members.filter((row) => matches(row, f)));
      return;
    }
    if (req.url?.startsWith("/rest/v1/entity_ownership")) {
      const f = filtersOf(req.url);
      if (req.method === "GET") {
        json(res, 200, ownership.filter((row) => matches(row, f)));
        return;
      }
      if (req.method === "POST") {
        void readBody(req).then((raw) => {
          const parsed = JSON.parse(raw) as unknown;
          // PostgREST takes either one object or an array; /api/publish sends
          // an array so a partial record is not a state it can end in.
          const incoming = (Array.isArray(parsed) ? parsed : [parsed]) as Record<
            string,
            unknown
          >[];
          const clash = incoming.some((row) =>
            ownership.some(
              (existing) =>
                existing["status"] === "active" &&
                existing["org_id"] === row["org_id"] &&
                existing["entity_type"] === row["entity_type"] &&
                existing["entity_uid"] === row["entity_uid"],
            ),
          );
          if (clash) {
            // What PostgREST returns for a unique index violation.
            json(res, 409, { code: "23505", message: "duplicate key value" });
            return;
          }
          const stored = incoming.map((row, i) => ({
            id: `claim-${ownership.length + i + 1}`,
            ...row,
          }));
          ownership.push(...stored);
          json(res, 201, stored);
        });
        return;
      }
      if (req.method === "PATCH") {
        void readBody(req).then((raw) => {
          const changes = JSON.parse(raw) as Record<string, unknown>;
          const hit = ownership.filter((row) => matches(row, f));
          for (const row of hit) Object.assign(row, changes);
          json(res, 200, hit);
        });
        return;
      }
    }
    res.statusCode = 404;
    res.end();
  });

  const port = await listen(server);
  const url = `http://127.0.0.1:${port}`;

  return {
    url,
    logInserts,
    feedbackInserts,
    members,
    ownership,
    promoterProfiles,
    rpcCalls,
    signToken: (opts: { sub?: string; role?: string; expiresIn?: string } = {}) =>
      new SignJWT(opts.role === undefined ? {} : { user_role: opts.role })
        .setProtectedHeader({ alg: "ES256", kid: "test-key" })
        .setIssuer(`${url}/auth/v1`)
        .setAudience("authenticated")
        .setSubject(opts.sub ?? "user-1")
        .setIssuedAt()
        .setExpirationTime(opts.expiresIn ?? "1h")
        .sign(privateKey),
    close: () => close(server),
  };
}

export interface SeenRequest {
  method: string;
  url: string;
  headers: Record<string, string | string[] | undefined>;
  body: string;
}

/**
 * Stub backend service. POST /chat/stream answers with a chunked SSE stream;
 * every other route echoes what it received (and records it in `seen`).
 */
export async function startUpstreamStub() {
  const seen: SeenRequest[] = [];
  // What POST /validate-event answers with. Left null, the request falls
  // through to the echo, so the existing proxy tests are unaffected.
  const publishState: { current: { status: number; body: unknown } | null } = {
    current: null,
  };
  // The retriever's by-uid entity lookups, which the claim route consults
  // before recording anything. Seeded by the test; an absent uid answers with
  // an empty list, which is the real endpoint's contract for a stale pointer.
  const entities: Record<string, { uid: string; name: string }[]> = {
    venues: [],
    artists: [],
    events: [],
  };

  const server = createServer((req: IncomingMessage, res: ServerResponse) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk: Buffer) => chunks.push(chunk));
    req.on("end", () => {
      const record: SeenRequest = {
        method: req.method ?? "",
        url: req.url ?? "",
        headers: req.headers,
        body: Buffer.concat(chunks).toString("utf8"),
      };
      seen.push(record);

      // Answering a lookup is opt-in: only a table the test seeded is served
      // here. Everything else - including a `q=` search and an unseeded
      // `uids=` - falls through to the echo, which is what the proxy tests
      // assert the query string survived intact.
      const lookup = /^\/(venues|artists|events)\?/.exec(req.url ?? "");
      const table = lookup?.[1] as keyof typeof entities | undefined;
      const asked = new URL(req.url ?? "", "http://x").searchParams.get("uids");
      if (table && req.method === "GET" && asked !== null && entities[table].length > 0) {
        const wanted = new Set(asked.split(",").filter(Boolean));
        res.writeHead(200, { "content-type": "application/json" });
        res.end(
          JSON.stringify({
            [table]: entities[table].filter((row) => wanted.has(row.uid)),
          }),
        );
        return;
      }

      if (
        req.url === "/validate-event" &&
        req.method === "POST" &&
        publishState.current !== null
      ) {
        res.writeHead(publishState.current.status, { "content-type": "application/json" });
        res.end(JSON.stringify(publishState.current.body));
        return;
      }

      if (req.url === "/chat/stream" && req.method === "POST") {
        res.writeHead(200, {
          "content-type": "text/event-stream",
          "cache-control": "no-cache",
        });
        const frames = ['data: {"delta": "hello"}\n\n', 'data: {"delta": " world"}\n\n', "data: [DONE]\n\n"];
        let i = 0;
        const timer = setInterval(() => {
          const frame = frames[i++];
          if (frame === undefined) {
            clearInterval(timer);
            res.end();
            return;
          }
          res.write(frame);
        }, 40);
        return;
      }

      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify(record));
    });
  });

  const port = await listen(server);
  return {
    url: `http://127.0.0.1:${port}`,
    seen,
    entities,
    publish: publishState,
    close: () => close(server),
  };
}

export function testConfig(overrides: Partial<GatewayConfig> & { supabaseUrl: string }): GatewayConfig {
  return {
    host: "127.0.0.1",
    port: 0,
    logLevel: "silent",
    retrieverUrl: "http://127.0.0.1:1",
    pusherUrl: "http://127.0.0.1:1",
    searchUrl: "http://127.0.0.1:1",
    searchEnabled: false,
    supabaseServiceRoleKey: "test-service-role-key",
    jwksUrl: `${overrides.supabaseUrl}/auth/v1/.well-known/jwks.json`,
    jwtIssuer: `${overrides.supabaseUrl}/auth/v1`,
    jwtAudience: "authenticated",
    corsAllowOrigins: ["http://localhost:8081"],
    internalApiKey: "",
    // No Redis in unit tests: the in-memory store is correct for one process.
    // Cross-replica quota is proved against a real cluster, not here.
    redisUrl: "",
    rateLimitWindowMs: 60_000,
    rateLimitAnonMax: 1000,
    rateLimitUserMax: 1000,
    rateLimitProMax: 1000,
    rateLimitAdminMax: 1000,
    // Small on purpose: the oversize test sends a few kB rather than 10 MB.
    uploadMaxBytes: 4096,
    conversationLogging: false,
    ...overrides,
  };
}
