import path from "node:path";
import dotenv from "dotenv";

export interface GatewayConfig {
  host: string;
  port: number;
  logLevel: string;
  retrieverUrl: string;
  pusherUrl: string;
  searchUrl: string;
  searchEnabled: boolean;
  supabaseUrl: string;
  supabaseServiceRoleKey: string;
  jwksUrl: string;
  jwtIssuer: string;
  jwtAudience: string;
  corsAllowOrigins: string[];
  rateLimitWindowMs: number;
  rateLimitAnonMax: number;
  rateLimitUserMax: number;
  conversationLogging: boolean;
}

const REQUIRED = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"] as const;

/**
 * Same convention as the Python services: a single root .env two levels up,
 * resolved against CWD — run from services/gateway. A missing file is fine
 * (Docker injects env directly); missing keys are not.
 */
export function loadConfig(env: NodeJS.ProcessEnv = process.env): GatewayConfig {
  dotenv.config({ path: process.env.ENV_FILE ?? path.resolve(process.cwd(), "../../.env") });

  const missing = REQUIRED.filter((key) => !env[key]);
  if (missing.length > 0) {
    throw new Error(
      `gateway config: missing required environment keys: ${missing.join(", ")}. ` +
        `Set them in the root .env (see .example.env).`,
    );
  }

  const supabaseUrl = env.SUPABASE_URL!.replace(/\/$/, "");

  return {
    host: env.GATEWAY_HOST ?? "0.0.0.0",
    port: Number(env.GATEWAY_PORT ?? 8000),
    logLevel: env.GATEWAY_LOG_LEVEL ?? "info",
    retrieverUrl: env.RETRIEVER_URL ?? "http://localhost:8002",
    pusherUrl: env.PUSHER_URL ?? "http://localhost:8003",
    searchUrl: env.SEARCH_URL ?? "http://localhost:8004",
    searchEnabled: env.SEARCH_ENABLED === "true",
    supabaseUrl,
    supabaseServiceRoleKey: env.SUPABASE_SERVICE_ROLE_KEY!,
    jwksUrl: env.SUPABASE_JWKS_URL ?? `${supabaseUrl}/auth/v1/.well-known/jwks.json`,
    jwtIssuer: env.SUPABASE_JWT_ISSUER ?? `${supabaseUrl}/auth/v1`,
    jwtAudience: env.SUPABASE_JWT_AUDIENCE ?? "authenticated",
    corsAllowOrigins: (env.CORS_ALLOW_ORIGINS ?? "http://localhost:8081")
      .split(",")
      .map((origin) => origin.trim())
      .filter(Boolean),
    rateLimitWindowMs: Number(env.RATE_LIMIT_WINDOW_MS ?? 60_000),
    rateLimitAnonMax: Number(env.RATE_LIMIT_ANON_MAX ?? 10),
    rateLimitUserMax: Number(env.RATE_LIMIT_USER_MAX ?? 60),
    conversationLogging: env.CONVERSATION_LOGGING !== "false",
  };
}
