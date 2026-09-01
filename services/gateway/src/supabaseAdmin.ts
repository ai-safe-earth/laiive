import type { GatewayConfig } from "./config.js";

/**
 * The service-role PostgREST client.
 *
 * `feedback.ts` and `logging.ts` each built the same four-header object and the
 * same `${supabaseUrl}/rest/v1/${table}` string inline. A third copy in
 * `orgs.ts` — which needs five verbs rather than one — is where that stops
 * being acceptable, so the shape moves here.
 *
 * The key goes in both `apikey` and `authorization`, which is what bypasses
 * RLS. Every policy in `20260819000011` is written for the *user's* JWT, so
 * authorization on these routes is entirely the route's own job: reaching this
 * client at all means the row-level rules have already been stepped over.
 */
export class PostgrestError extends Error {
  constructor(
    readonly status: number,
    readonly body: string,
  ) {
    super(`postgrest ${status}: ${body.slice(0, 200)}`);
    this.name = "PostgrestError";
  }

  /** 23505 — a unique index rejected the row. The routes map this to 409. */
  get isUniqueViolation(): boolean {
    return this.status === 409 || this.body.includes("23505");
  }
}

export interface SupabaseAdmin {
  select<T>(table: string, query: string): Promise<T[]>;
  insert<T>(table: string, row: unknown): Promise<T>;
  patch<T>(table: string, query: string, changes: unknown): Promise<T[]>;
  rpc<T>(fn: string, args: Record<string, unknown>): Promise<T>;
}

export function createSupabaseAdmin(config: GatewayConfig): SupabaseAdmin {
  const base = `${config.supabaseUrl}/rest/v1`;
  const headers = {
    "content-type": "application/json",
    apikey: config.supabaseServiceRoleKey,
    authorization: `Bearer ${config.supabaseServiceRoleKey}`,
  };

  // Awaited and throwing, unlike logging.ts's fire-and-forget hook: these sit
  // on a request/response path, so the caller has to learn that the write
  // failed rather than return 204 over a lost row.
  async function call(url: string, init: RequestInit): Promise<Response> {
    const response = await fetch(url, init);
    if (!response.ok) {
      throw new PostgrestError(response.status, await response.text());
    }
    return response;
  }

  return {
    async select<T>(table: string, query: string): Promise<T[]> {
      const response = await call(`${base}/${table}?${query}`, { headers });
      return (await response.json()) as T[];
    },

    async insert<T>(table: string, row: unknown): Promise<T> {
      const response = await call(`${base}/${table}`, {
        method: "POST",
        headers: { ...headers, prefer: "return=representation" },
        body: JSON.stringify(row),
      });
      const rows = (await response.json()) as T[];
      // PostgREST answers an insert with an array even for one row.
      return rows[0] as T;
    },

    async patch<T>(table: string, query: string, changes: unknown): Promise<T[]> {
      const response = await call(`${base}/${table}?${query}`, {
        method: "PATCH",
        headers: { ...headers, prefer: "return=representation" },
        body: JSON.stringify(changes),
      });
      return (await response.json()) as T[];
    },

    async rpc<T>(fn: string, args: Record<string, unknown>): Promise<T> {
      const response = await call(`${base}/rpc/${fn}`, {
        method: "POST",
        headers,
        body: JSON.stringify(args),
      });
      return (await response.json()) as T;
    },
  };
}
