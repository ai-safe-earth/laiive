/**
 * Where to land once a session exists.
 *
 * OAuth leaves the app entirely and comes back as a fresh document, so nothing
 * in component state survives the round trip. `redirectTo` is the proper way to
 * carry the intent, but Supabase only honours a value its Redirect URLs
 * allow-list matches and silently substitutes the Site URL when it does not —
 * which is invisible from the client and cannot be checked from outside the
 * dashboard. This is the belt to that pair of braces: the intent is written
 * down before leaving and read back on return, so a promoter reaches /pro
 * whether or not the allow-list has been widened.
 *
 * sessionStorage rather than localStorage: the OAuth redirect returns to the
 * same tab, and an intent that outlived the tab would ambush a later sign-in.
 */
const KEY = "laiive-post-auth";

/** Remember a destination across the OAuth round trip. "/" is the default and
 *  needs no stash — writing it would only create something to clean up. */
export function rememberDestination(path: string): void {
  if (path === "/") return;
  try {
    sessionStorage.setItem(KEY, path);
  } catch {
    // Private mode and blocked storage both throw. The redirectTo path still
    // works, and losing the fallback is not worth failing the sign-in over.
  }
}

/** Read the destination and forget it, so it can only ever be honoured once. */
export function takeDestination(): string | null {
  try {
    const path = sessionStorage.getItem(KEY);
    if (path) sessionStorage.removeItem(KEY);
    return path;
  } catch {
    return null;
  }
}
