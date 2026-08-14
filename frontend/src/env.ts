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
  // Everything application-side goes through the gateway (Phase 3). Supabase is
  // reached directly for auth and for the user's own profile rows, which RLS
  // scopes to them (src/api/profile.ts).
  apiUrl: required("VITE_API_URL").replace(/\/$/, ""),
  supabaseUrl: required("VITE_SUPABASE_URL").replace(/\/$/, ""),
  supabasePublishableKey: required("VITE_SUPABASE_PUBLISHABLE_KEY"),
};
