import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/auth/AuthProvider";
import { Mark } from "@/components/Mark";
import { useTranslation } from "@/i18n/useTranslation";

/**
 * The waiting room OAuth returns to.
 *
 * Google used to come back straight to the destination, which for the promoter
 * door is /pro — a page that reads the role off the token and refuses anyone
 * without it. The grant and the re-minted token land a moment later, so the
 * promoter was shown a refusal for their trouble and then watched it flip.
 * This page renders nothing role-gated; PostAuthLanding finishes the setup and
 * forwards from here, so /pro is only ever reached with a token that says pro.
 *
 * Neutral, not the pro theme: consumers come back through here too, and it is
 * on screen for as long as one round trip to Supabase takes.
 */
export default function AuthCallback() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();

  useEffect(() => {
    if (isLoading || user) return;
    // No session came back: a cancelled consent screen, a provider error, or
    // somebody typing this URL. PostAuthLanding only acts on a user, so
    // without this the waiting room waits forever.
    const params = new URLSearchParams(
      window.location.hash.startsWith("#") ? window.location.hash.slice(1) : window.location.search,
    );
    const description = params.get("error_description");
    if (params.get("error")) toast.error(description ?? t.auth.googleFailed);
    navigate("/auth", { replace: true });
    // t is read, not tracked: the language cannot change on a screen with no
    // controls, and re-running would only re-navigate.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, user, navigate]);

  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-4 bg-background p-6 text-center">
      <Mark size={30} />
      <p className="font-mono text-xs uppercase tracking-[0.11em] text-ink-dim">
        {t.auth.finishing}
      </p>
    </div>
  );
}
