import { env } from "@/env";
import { supabase } from "@/auth/supabase";

/** Everything the UI needs to react to a non-200 from the gateway. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** Set when the gateway invited an anonymous caller to sign in. */
    readonly loginUpsell = false,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Single entry point to the gateway (:8000). The services are not reachable
 * from the browser any more (Phase 3), so every call goes through /api/*.
 *
 * The access token is read per request rather than captured once: supabase-js
 * refreshes it in the background and a stale closure would send an expired JWT,
 * which the gateway rejects with 401 rather than downgrading to anonymous.
 */
export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("content-type", "application/json");

  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (token) headers.set("authorization", `Bearer ${token}`);

  const response = await fetch(`${env.apiUrl}${path}`, { ...init, headers });

  if (!response.ok) {
    throw new ApiError(
      response.status,
      await errorMessage(response),
      response.headers.get("x-login-upsell") !== null,
    );
  }
  return response;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { message?: string; error?: string };
    return body.message ?? body.error ?? `request failed (${response.status})`;
  } catch {
    return `request failed (${response.status})`;
  }
}
