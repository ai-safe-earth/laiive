import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import { acceptInvitation, orgKeys } from "@/api/organizations";
import { useAuth } from "@/auth/AuthProvider";
import { PromoterRefreshError, refreshRole } from "@/auth/becomePromoter";
import { Mark } from "@/components/Mark";
import { Button } from "@/components/ui/Button";
import { useTranslation } from "@/i18n/useTranslation";

/**
 * Where an invitation link lands.
 *
 * There is no mail provider in this project, so the link travels by whatever
 * channel the admin used — which means this page is reached cold, often by
 * somebody with no account at all, and it has to work for each of them:
 *
 *  - signed out: stash the destination and send them through the front door,
 *    exactly as the promoter door does for OAuth. PostAuthLanding forwards
 *    back here once a session exists, and the accept fires on the second pass.
 *  - signed in: redeem, re-mint the token, and go to the organisation.
 *
 * The token is spent once. A failure that is not worth retrying says so and
 * offers a way out rather than looping — a link nobody can redeem is a dead
 * end, and the useful thing is to say which one it is.
 */
export default function Invite() {
  const { token } = useParams<{ token: string }>();
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const [failure, setFailure] = useState<string | null>(null);
  // Effects run twice under StrictMode in development, and this one spends a
  // single-use token — the second pass would report "already accepted" over a
  // success. The ref makes the attempt happen once per mount.
  const attempted = useRef(false);

  useEffect(() => {
    if (isLoading || !token) return;
    // Before the signed-out branch, not after: redeeming ends with a session
    // refresh, and a token being re-minted can read as "no user" for a tick.
    // Checked second, that tick would stash the spent link and bounce somebody
    // who has just joined back to the sign-in screen.
    if (attempted.current) return;

    if (!user) {
      // In the URL, not in the sessionStorage stash. /auth clears that stash on
      // mount by design — a leftover destination there means an abandoned round
      // trip — and googleSignIn then overwrites it with its own. A caller that
      // writes it before navigating here loses it twice, silently, which is
      // exactly what a stashed invitation did: sign in, land on the chat, and
      // never join anything.
      navigate(`/auth?next=${encodeURIComponent(`/invite/${token}`)}`, { replace: true });
      return;
    }

    attempted.current = true;

    const run = async () => {
      let accepted;
      try {
        accepted = await acceptInvitation(token);
      } catch (error) {
        setFailure(messageFor(error, t));
        return;
      }

      // The seat exists; only the JWT disagrees. The user_role claim is stamped
      // at issue, so without re-minting, a guest who has just become a promoter
      // is refused by /pro for up to an hour — the same half that
      // becomePromoter handles for the sign-up path.
      try {
        await refreshRole();
      } catch (error) {
        if (!(error instanceof PromoterRefreshError)) throw error;
        // Not a failure of the invitation: they are in the organisation and
        // the database says so. Say what happened and let them land on
        // /account, which does not read the role off the token.
        toast.error(t.invite.staleSession);
        navigate("/account", { replace: true });
        return;
      }

      // The new seat changes what /pro/org lists, and the org list is keyed by
      // user — without this the page it forwards to renders the old answer.
      void queryClient.invalidateQueries({ queryKey: orgKeys.mine(user.id) });
      toast.success(accepted.already ? t.invite.alreadyIn : t.invite.welcome);
      // replace, so the back button does not return to a spent token, and the
      // token stops being the current URL.
      navigate("/pro/org", { replace: true });
    };
    void run();
    // t is read, not tracked: re-running would re-spend the token.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, user, token, navigate, queryClient]);

  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-4 bg-pro-bg p-6 text-center">
      <Mark size={30} />
      {failure ? (
        <>
          <p className="max-w-sm text-md leading-[1.5] text-pro-muted">{failure}</p>
          <Button variant="proNeutral" onClick={() => navigate("/")}>
            {t.invite.leave}
          </Button>
        </>
      ) : (
        <p className="font-mono text-xs uppercase tracking-[0.11em] text-pro-dim">
          {t.invite.joining}
        </p>
      )}
    </div>
  );
}

/** Every way a link fails, in the words the holder needs to hear. */
function messageFor(error: unknown, t: ReturnType<typeof useTranslation>["t"]): string {
  if (!(error instanceof ApiError)) return t.invite.failed;
  if (error.status === 404) return t.invite.unknown;
  if (error.status === 409) return t.invite.spent;
  if (error.status === 410) return t.invite.expired;
  // The gateway names the invited address in this one, which is the whole point
  // of the message: it says which account to sign in as.
  if (error.status === 403) return error.message;
  return t.invite.failed;
}
