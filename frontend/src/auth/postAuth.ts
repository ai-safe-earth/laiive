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
 * The one exception is the pending promoter at the bottom of this file, which
 * has to survive a mail client — see the note there.
 */
const KEY = "laiive-post-auth";

/** The page OAuth returns to. It exists so that nothing role-gated renders
 *  before the promoter row and the re-minted token have both landed. */
export const CALLBACK_PATH = "/auth/callback";

/** Remember a destination across the OAuth round trip. "/" is stashed like any
 *  other: the return now lands on CALLBACK_PATH, which is a waiting room and
 *  never a destination, so it always needs somewhere to send the visitor on. */
export function rememberDestination(path: string): void {
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

/**
 * The organisation a promoter typed on the way out, for the same reason and
 * with the same lifetime as the destination above: OAuth leaves the app, and
 * the name they gave has to be there when the session comes back so signing up
 * as a promoter is one form rather than an account followed by an application.
 */
const ORG_KEY = "laiive-post-auth-org";

export function rememberPromoterOrg(orgName: string): void {
  const trimmed = orgName.trim();
  if (!trimmed) return;
  try {
    sessionStorage.setItem(ORG_KEY, trimmed);
  } catch {
    // Same trade as the destination: losing the fallback must not fail sign-in.
    // The promoter can still fill the form on /account.
  }
}

/** Read the organisation and forget it — consumed exactly once, like above. */
export function takePromoterOrg(): string | null {
  try {
    const org = sessionStorage.getItem(ORG_KEY);
    if (org) sessionStorage.removeItem(ORG_KEY);
    return org;
  } catch {
    return null;
  }
}

/** Both round-trip stashes at once, for the screen that clears an abandoned
 *  attempt. Deliberately not the pending promoter below: that one is not a
 *  round trip in flight, and reaching /auth again is exactly what happens
 *  while waiting for the confirmation mail. */
export function clearPostAuth(): void {
  takeDestination();
  takePromoterOrg();
}

/**
 * A promoter who signed up while "Confirm email" is on.
 *
 * There is no session to write the promoter row into, and the confirmation
 * link is opened from a mail client — a different tab, often a different
 * window — so sessionStorage is gone by the time a session exists. Without
 * this the organisation they typed is simply discarded and the door goes back
 * to producing ordinary accounts, which is the bug the door was built to fix.
 *
 * localStorage, therefore, keyed to the address it was typed for: it is spent
 * only when a session appears for that same person. It also expires, because
 * an intent with no lifetime is an ambush waiting for whoever signs in next.
 */
const PENDING_KEY = "laiive-pending-promoter";
const PENDING_TTL_MS = 24 * 60 * 60 * 1000;

interface PendingPromoter {
  email: string;
  org: string;
  at: number;
}

export function rememberPendingPromoter(email: string, orgName: string): void {
  const org = orgName.trim();
  const who = email.trim().toLowerCase();
  if (!org || !who) return;
  try {
    const pending: PendingPromoter = { email: who, org, at: Date.now() };
    localStorage.setItem(PENDING_KEY, JSON.stringify(pending));
  } catch {
    // Same trade as everything above: never fail a sign-up over a stash.
  }
}

/**
 * The organisation waiting for this address, if any — read once and forgotten.
 * A mismatch is left in place: it belongs to someone else's confirmation, and
 * this sign-in has no business spending it.
 */
export function takePendingPromoter(email: string | undefined): string | null {
  const who = email?.trim().toLowerCase();
  try {
    const raw = localStorage.getItem(PENDING_KEY);
    if (!raw) return null;
    const pending = JSON.parse(raw) as PendingPromoter;
    if (Date.now() - pending.at > PENDING_TTL_MS) {
      localStorage.removeItem(PENDING_KEY);
      return null;
    }
    if (!who || pending.email !== who) return null;
    localStorage.removeItem(PENDING_KEY);
    return pending.org || null;
  } catch {
    // Unreadable or malformed: drop it rather than let it sit and re-throw
    // on every sign-in for the rest of the browser's life.
    try {
      localStorage.removeItem(PENDING_KEY);
    } catch {
      // Nothing left to do; the caller treats this as "no pending intent".
    }
    return null;
  }
}
