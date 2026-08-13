import { createClient } from "@supabase/supabase-js";
import { env } from "@/env";

/**
 * Auth only — this client never reads application tables. Profile and role data
 * reach the browser through the gateway, which holds the service role key.
 */
export const supabase = createClient(env.supabaseUrl, env.supabasePublishableKey, {
  auth: {
    storage: localStorage,
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});

export type UserRole = "user" | "pro" | "admin";

/**
 * The role lives in the `user_role` claim stamped by the custom access token
 * hook (supabase/migrations/20260813000002_user_roles.sql). Supabase's own
 * `role` claim is the Postgres role ("authenticated") and means nothing here —
 * the gateway ignores it too.
 */
export function roleFromToken(accessToken: string | undefined): UserRole {
  if (!accessToken) return "user";
  try {
    const payload = accessToken.split(".")[1];
    if (!payload) return "user";
    const claims = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/"))) as {
      user_role?: string;
    };
    return claims.user_role === "pro" || claims.user_role === "admin"
      ? claims.user_role
      : "user";
  } catch {
    return "user";
  }
}
