/**
 * Client for the pusher service (event creation / promoter tools).
 * Calls the FastAPI backend directly instead of Supabase Edge Functions.
 */

const PUSHER_URL = import.meta.env.VITE_PUSHER_URL as string;

export interface PusherFetchOptions {
  signal?: AbortSignal;
}

/**
 * POST to the pusher service. Returns the raw Response (for SSE streaming).
 */
export async function pusherFetch(
  path: string,
  body: unknown,
  opts: PusherFetchOptions = {},
): Promise<Response> {
  const response = await fetch(`${PUSHER_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: opts.signal,
  });
  return response;
}

/**
 * POST to the pusher service and parse the JSON response.
 */
export async function pusherFetchJSON<T = unknown>(
  path: string,
  body: unknown,
  opts: PusherFetchOptions = {},
): Promise<T> {
  const response = await pusherFetch(path, body, opts);
  if (!response.ok) {
    throw new Error(`Pusher ${path} failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}
