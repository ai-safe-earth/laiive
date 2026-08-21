import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/auth/AuthProvider";
import { becomePromoter, PromoterRefreshError } from "@/auth/becomePromoter";
import {
  CALLBACK_PATH,
  takeDestination,
  takePendingPromoter,
  takePromoterOrg,
} from "@/auth/postAuth";
import { useTranslation } from "@/i18n/useTranslation";

/**
 * OAuth comes back to whichever URL Supabase's allow-list permitted, which is
 * not necessarily where the promoter started. Once a session exists, honour
 * what they left with — the destination, and for the promoter's door the
 * organisation, since there was no session to write it into on the way out.
 * Both are spent once, and the destination only if we are not already on it.
 *
 * Renders nothing; it exists to be inside the router, where `navigate` works.
 */
export function PostAuthLanding() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { t } = useTranslation();

  useEffect(() => {
    if (isLoading || !user) return;
    const destination = takeDestination();
    // Two ways the promoter door's organisation reaches a session: in this tab,
    // if OAuth went out and came back, or waiting for the address, if a
    // confirmation mail stood between the form and the first session.
    const orgName = takePromoterOrg() ?? takePendingPromoter(user.email);

    // Before navigating: /pro reads the role off the token, and becomePromoter
    // is what re-mints it. Landing there first would show the refusal screen to
    // someone who is about to become a promoter, then flip under them.
    const run = async () => {
      // The callback route is a waiting room, never somewhere to be left: if
      // the stash was lost, the chat is still a place to be. A promoter who
      // confirmed a mail has no stash at all — their door was /pro.
      let target = destination ?? (pathname === CALLBACK_PATH ? "/" : null);
      if (orgName) {
        target = target ?? "/pro";
        try {
          await becomePromoter(user.id, orgName);
        } catch (error) {
          // The account is real and signed in either way — say so and let them
          // finish on /account rather than stranding them on a refusal. Which
          // half failed changes the wording, not the destination: a promoter
          // whose token was not re-minted is refused by /pro just the same.
          toast.error(
            error instanceof PromoterRefreshError
              ? t.auth.promoterSessionStale
              : t.auth.promoterSetupFailed,
          );
          target = "/account";
        }
      }
      if (target && target !== pathname) navigate(target, { replace: true });
    };
    void run();
    // pathname and t are read, not tracked: re-running on navigation would
    // re-enter with the stashes already spent, and only risks a second navigate.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, user, navigate]);

  return null;
}
