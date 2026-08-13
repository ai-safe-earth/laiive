/**
 * Typed, runtime-validated environment. Vite inlines these at build time, so a
 * missing key is a blank screen in production unless we fail loudly here — the
 * same contract the Python services and the gateway hold themselves to.
 */
interface Env {
  apiUrl: string;
  supabaseUrl: string;
  supabasePublishableKey: string;
}

function required(name: keyof ImportMetaEnv): string {
  const value = import.meta.env[name];
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(
      `Missing ${String(name)} — copy .env.example to .env and fill it in (see frontend/README.md).`,
    );
  }
  return value;
}

export const env: Env = {
  // The gateway is the only backend the browser talks to (Phase 3).
  apiUrl: required("VITE_API_URL").replace(/\/$/, ""),
  supabaseUrl: required("VITE_SUPABASE_URL").replace(/\/$/, ""),
  supabasePublishableKey: required("VITE_SUPABASE_PUBLISHABLE_KEY"),
};
