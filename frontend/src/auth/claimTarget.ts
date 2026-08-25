import type { UserRole } from "./supabase";

/**
 * Where a card's claim invitation sends this reader: the promoter door for
 * whoever they are today. Signed out, the promoter sign-up; signed in without
 * the role, the account screen that grants it; a promoter, their own surface.
 *
 * Lives beside the auth types rather than on the card so the card stays
 * presentational and the promoter predicate is typed against UserRole.
 */
export function claimTarget(signedIn: boolean, role: UserRole | null): string {
  if (!signedIn) return "/auth?kind=pro";
  return role === "pro" || role === "admin" ? "/pro" : "/account";
}
