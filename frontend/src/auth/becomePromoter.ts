import { supabase } from "./supabase";

/**
 * The row landed, the token did not. Thrown apart from every other failure
 * because it means something different to the caller: this account *is* a
 * promoter, the database says so, and only the JWT in this browser disagrees.
 * Sending them to /pro on that stale claim is the refusal screen again, so the
 * caller routes elsewhere and says what actually happened.
 */
export class PromoterRefreshError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PromoterRefreshError";
  }
}

/**
 * Turn a signed-in account into a promoter account.
 *
 * Writing the promoter_profiles row is the grant: the trigger from
 * 20260820000012 promotes 'user' to 'pro' on insert. The client never touches
 * user_roles — it has no policy to, deliberately — it writes the one row RLS
 * lets it own, and the database decides what that means.
 *
 * Both halves matter. The role rides in the JWT's user_role claim, stamped at
 * issue, so without re-minting the token a promoter who just became one keeps
 * being refused for up to an hour. Same reason /account refreshes after its own
 * save; this is that step for the sign-up path.
 *
 * Callers own the failure, and the two halves fail differently — see
 * PromoterRefreshError. Neither is a reason to bounce someone back to a
 * sign-up screen: the account exists and is usable either way.
 */
export async function becomePromoter(userId: string, orgName: string): Promise<void> {
  const org = orgName.trim();
  if (!org) throw new Error("organisation is required");

  const { error } = await supabase.from("promoter_profiles").upsert(
    { user_id: userId, org_name: org, updated_at: new Date().toISOString() },
    { onConflict: "user_id" },
  );
  if (error) throw new Error(error.message);

  // Past this line the grant has happened. A refresh that fails is a network
  // blip far more often than anything structural, so try once more before
  // telling anyone their sign-up went wrong — it did not.
  const { error: refreshError } = await supabase.auth.refreshSession();
  if (!refreshError) return;

  const { error: retryError } = await supabase.auth.refreshSession();
  if (retryError) throw new PromoterRefreshError(retryError.message);
}
