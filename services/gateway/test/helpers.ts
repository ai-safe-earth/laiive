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

  const server = createServer((req: IncomingMessage, res: ServerResponse) => {
    if (req.url === "/auth/v1/.well-known/jwks.json") {
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ keys: [jwk] }));
      return;
    }
    if (req.url === "/rest/v1/conversation_logs" && req.method === "POST") {
      const chunks: Buffer[] = [];
      req.on("data", (chunk: Buffer) => chunks.push(chunk));
      req.on("end", () => {
        logInserts.push(JSON.parse(Buffer.concat(chunks).toString("utf8")));
        res.statusCode = 201;
        res.end();
      });
      return;
    }
    res.statusCode = 404;
    res.end();
  });

  const port = await listen(server);
  const url = `http://127.0.0.1:${port}`;

  return {
    url,
    logInserts,
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
  return { url: `http://127.0.0.1:${port}`, seen, close: () => close(server) };
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
    rateLimitWindowMs: 60_000,
    rateLimitAnonMax: 1000,
    rateLimitUserMax: 1000,
    // Small on purpose: the oversize test sends a few kB rather than 10 MB.
    uploadMaxBytes: 4096,
    conversationLogging: false,
    ...overrides,
  };
}
