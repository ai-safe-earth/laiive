/**
 * Client for the retriever service (event search / chat).
 * Calls the FastAPI backend directly instead of Supabase Edge Functions.
 */

const RETRIEVER_URL = import.meta.env.VITE_RETRIEVER_URL as string;

export interface RetrieverFetchOptions {
  signal?: AbortSignal;
}

/**
 * POST to the retriever service. Returns the raw Response (for SSE streaming).
 */
export async function retrieverFetch(
  path: string,
  body: unknown,
  opts: RetrieverFetchOptions = {},
): Promise<Response> {
  const response = await fetch(`${RETRIEVER_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: opts.signal,
  });
  return response;
}

/**
 * POST to the retriever service and parse the JSON response.
 */
export async function retrieverFetchJSON<T = unknown>(
  path: string,
  body: unknown,
  opts: RetrieverFetchOptions = {},
): Promise<T> {
  const response = await retrieverFetch(path, body, opts);
  if (!response.ok) {
    throw new Error(`Retriever ${path} failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}
