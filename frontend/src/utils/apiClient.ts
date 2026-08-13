/**
 * Thin wrapper around fetch for Supabase function calls.
 */

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string;

export interface FetchOptions {
  /** Use the user's access token instead of the anon key */
  accessToken?: string;
  signal?: AbortSignal;
}

/**
 * Call a Supabase Edge Function. Returns the raw Response for streaming,
 * or throws on non-OK status.
 */
export async function callFunction(
  functionName: string,
  body: unknown,
  opts: FetchOptions = {},
): Promise<Response> {
  const token = opts.accessToken || SUPABASE_ANON_KEY;

  const response = await fetch(
    `${SUPABASE_URL}/functions/v1/${functionName}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
      signal: opts.signal,
    },
  );

  return response;
}

/**
 * Call a Supabase Edge Function and parse the JSON response.
 */
export async function callFunctionJSON<T = unknown>(
  functionName: string,
  body: unknown,
  opts: FetchOptions = {},
): Promise<T> {
  const response = await callFunction(functionName, body, opts);
  if (!response.ok) {
    throw new Error(`${functionName} failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}
