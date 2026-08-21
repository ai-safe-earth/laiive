import { supabase } from "./supabase";

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
 * Callers own the failure: the account exists and is usable either way, so a
 * promoter whose row did not land should be let in and told to finish on
 * /account, never bounced back to a sign-up screen.
 */
export async function becomePromoter(userId: string, orgName: string): Promise<void> {
  const org = orgName.trim();
  if (!org) throw new Error("organisation is required");

  const { error } = await supabase.from("promoter_profiles").upsert(
    { user_id: userId, org_name: org, updated_at: new Date().toISOString() },
    { onConflict: "user_id" },
  );
  if (error) throw new Error(error.message);

  const { error: refreshError } = await supabase.auth.refreshSession();
  if (refreshError) throw new Error(refreshError.message);
}
