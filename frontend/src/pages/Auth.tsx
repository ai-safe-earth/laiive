import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/auth/AuthProvider";
import { becomePromoter, PromoterRefreshError } from "@/auth/becomePromoter";
import {
  CALLBACK_PATH,
  clearPostAuth,
  rememberDestination,
  rememberPendingPromoter,
  rememberPromoterOrg,
} from "@/auth/postAuth";
import { Mark } from "@/components/Mark";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useTranslation } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

type Mode = "signin" | "signup";

export default function Auth() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { signIn, signInWithGoogle, signUp } = useAuth();

  // `?kind=pro` is the promoter's door, and it now finishes the job. It used to
  // create an ordinary account and land on /pro, which refused it and sent the
  // promoter to /account to fill a second form — the door made you apply for
  // what you had just walked through it to get. Asking for the organisation
  // here means one form: the account and the promoter row are written together,
  // the trigger grants the role, and /pro opens.
  const [params] = useSearchParams();
  const isPro = params.get("kind") === "pro";

  const [mode, setMode] = useState<Mode>(isPro ? "signup" : "signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [busy, setBusy] = useState(false);
  // Held apart from `busy`: a form submit clears itself in a `finally`, but the
  // OAuth hand-off never returns, so only coming back to this page can clear it.
  // Sharing one flag meant tabbing away mid-submit would re-enable the button.
  const [redirecting, setRedirecting] = useState(false);

  // Abandoning the Google screen and pressing back restores this page from the
  // bfcache with its state intact, so `redirecting` stayed true and the whole
  // form was left dead — no Google button, and a submit button whose disabled
  // fill matched the card behind it, so it read as missing rather than off.
  // Two triggers, because the browsers disagree about which one you get back:
  // `pageshow` covers a bfcache restore (the back button), `visibilitychange`
  // covers returning without one — an in-app browser, or an app switch on a
  // phone. Clearing it twice is harmless; never clearing it kills the screen.
  useEffect(() => {
    // Reaching this screen at all means no round trip is in flight, so any
    // stashed destination is left over from an abandoned one. Cleared on mount
    // as well as on the events below, because `pageshow` has already fired by
    // the time React attaches to it on a fresh document — which left the stash
    // alive to ambush the next sign-in, one made by email minutes later.
    clearPostAuth();

    const revive = () => {
      if (document.visibilityState !== "visible") return;
      setRedirecting(false);
      clearPostAuth();
    };
    window.addEventListener("pageshow", revive);
    document.addEventListener("visibilitychange", revive);
    return () => {
      window.removeEventListener("pageshow", revive);
      document.removeEventListener("visibilitychange", revive);
    };
  }, []);

  // Where this sign-in is headed. The promoter's door has to survive OAuth,
  // which leaves the app and returns as a fresh document.
  const destination = isPro ? "/pro" : "/";

  const googleSignIn = async () => {
    if (isPro && mode === "signup" && !orgName.trim()) {
      toast.error(t.auth.orgRequired);
      return;
    }
    setRedirecting(true);
    try {
      rememberDestination(destination);
      // The organisation cannot be written yet — there is no session until
      // Google hands one back — so it travels the same way the destination
      // does, and PostAuthLanding spends it once the account exists.
      if (isPro && mode === "signup") rememberPromoterOrg(orgName);
      // Not `destination`: coming back straight to /pro renders the refusal
      // screen against a token that has not been re-minted yet, then flips
      // under the promoter a moment later. The callback is a waiting room —
      // it holds until the row and the token have both landed, then forwards.
      // Resolves before the browser leaves, so this stays on until it does.
      await signInWithGoogle(`${window.location.origin}${CALLBACK_PATH}`);
    } catch (error) {
      clearPostAuth();
      toast.error(error instanceof Error ? error.message : t.auth.googleFailed);
      setRedirecting(false);
    }
  };

  const frozen = busy || redirecting;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    // Before the account exists, not after: `required` is happy with a space,
    // and becomePromoter is not — which used to create an ordinary account,
    // fail the grant, and land the new non-promoter on /pro to be refused.
    if (isPro && mode === "signup" && !orgName.trim()) {
      toast.error(t.auth.orgRequired);
      return;
    }
    setBusy(true);
    try {
      if (mode === "signin") {
        await signIn(email, password);
        navigate(destination);
      } else {
        // With "Confirm email" off, sign-up returns a live session and the
        // account is already usable — telling that person to check an inbox
        // sends them to wait for a mail Supabase never attempted to send, and
        // then lets them in anyway. Follow what came back, not what we assume.
        const { signedIn, userId } = await signUp(email, password, displayName || undefined);
        if (!signedIn) {
          // Confirmation is on, so there is no session to write the promoter
          // row into and the mail will be opened somewhere this tab cannot
          // reach. The organisation waits for the address instead, and the
          // first session that belongs to it spends the intent.
          if (isPro) rememberPendingPromoter(email, orgName);
          toast.success(t.auth.checkInbox);
          setMode("signin");
          return;
        }
        if (isPro && userId) {
          // Deliberately not fatal. The account exists and works; a promoter
          // row that failed to land is a finishable state on /account, not a
          // reason to throw someone back at a sign-up form they just completed.
          // A failed *refresh* is a third thing again: they are a promoter, the
          // token in this tab just does not say so yet, and /pro would refuse
          // them on it — so both failures finish on /account.
          try {
            await becomePromoter(userId, orgName);
          } catch (error) {
            toast.error(
              error instanceof PromoterRefreshError
                ? t.auth.promoterSessionStale
                : t.auth.promoterSetupFailed,
            );
            navigate("/account");
            return;
          }
        }
        navigate(destination);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.auth.failed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={cn("flex min-h-[100dvh] flex-col items-center justify-center p-6", isPro ? "bg-pro-bg" : "bg-background")}>
      <Link to="/" className="mb-8 flex items-center gap-2.5">
        <Mark size={30} />
        {isPro && (
          <span className="rounded-full border border-pro-accent/45 bg-pro-accent/[0.12] px-2 py-[5px] font-mono text-[9.5px] font-medium uppercase leading-none tracking-[0.11em] text-pro-accent">
            pro
          </span>
        )}
      </Link>

      <form
        onSubmit={submit}
        className={cn(
          "flex w-full max-w-sm flex-col gap-4 rounded-[26px] border p-6",
          isPro ? "border-pro-border bg-pro-card" : "border-hairline/[0.07] bg-card",
        )}
      >
        <h1 className={cn("font-bebas text-[24px] leading-none tracking-[0.04em]", isPro ? "text-pro-fg" : "text-card-foreground")}>
          {mode === "signin" ? t.auth.signInTitle : t.auth.signUpTitle}
        </h1>

        {mode === "signup" && (
          <Input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder={t.auth.displayNamePlaceholder}
            autoComplete="nickname"
          />
        )}

        {/* The one field that makes this the promoter's door rather than a
            consumer sign-up wearing a badge: it is what grants the role. */}
        {isPro && mode === "signup" && (
          <Input
            required
            value={orgName}
            onChange={(event) => setOrgName(event.target.value)}
            placeholder={t.auth.orgPlaceholder}
            autoComplete="organization"
          />
        )}

        <Input
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder={t.auth.emailPlaceholder}
          autoComplete="email"
        />
        <Input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder={t.auth.passwordPlaceholder}
          autoComplete={mode === "signin" ? "current-password" : "new-password"}
        />

        <Button type="submit" className="w-full" disabled={frozen}>
          {frozen ? "…" : mode === "signin" ? t.auth.signIn : t.auth.signUp}
        </Button>

        <div className="flex items-center gap-3 font-mono text-[11px] text-ink-dim">
          <span className="h-px flex-1 bg-border" />
          {t.auth.or}
          <span className="h-px flex-1 bg-border" />
        </div>

        <Button
          type="button"
          variant="neutral"
          className="w-full"
          disabled={frozen}
          onClick={googleSignIn}
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
            <path
              fill="#4285F4"
              d="M23.5 12.27c0-.85-.08-1.66-.22-2.45H12v4.64h6.45a5.52 5.52 0 0 1-2.39 3.62v3h3.87c2.26-2.09 3.57-5.17 3.57-8.81Z"
            />
            <path
              fill="#34A853"
              d="M12 24c3.24 0 5.96-1.07 7.93-2.91l-3.87-3.01c-1.07.72-2.45 1.15-4.06 1.15-3.12 0-5.77-2.11-6.71-4.95H1.29v3.1A11.99 11.99 0 0 0 12 24Z"
            />
            <path
              fill="#FBBC05"
              d="M5.29 14.28A7.21 7.21 0 0 1 4.91 12c0-.79.14-1.56.38-2.28v-3.1H1.29a12 12 0 0 0 0 10.76l4-3.1Z"
            />
            <path
              fill="#EA4335"
              d="M12 4.77c1.76 0 3.34.61 4.58 1.8l3.44-3.44C17.95 1.19 15.24 0 12 0A11.99 11.99 0 0 0 1.29 6.62l4 3.1C6.23 6.88 8.88 4.77 12 4.77Z"
            />
          </svg>
          {t.auth.google}
        </Button>

        <button
          type="button"
          onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
          className="w-full py-1 text-center text-[12.5px] text-muted-foreground transition-colors hover:text-foreground"
        >
          {mode === "signin" ? t.auth.toSignUp : t.auth.toSignIn}
        </button>
      </form>

      {/* The promoter's door. Cyan is theirs, and it only appears when the
          visitor is not already coming through it. */}
      {!isPro && (
        <div className="mt-6 flex w-full max-w-sm flex-col items-center gap-1 text-center">
          <p className="text-[12.5px] leading-[1.4] text-muted-foreground">{t.auth.proInvite}</p>
          <Link
            to="/auth?kind=pro"
            className="text-[13px] leading-[1.4] text-pro-accent transition-opacity hover:opacity-80"
          >
            {t.auth.proCta}
          </Link>
        </div>
      )}

      <Link
        to="/"
        className="mt-6 text-[12.5px] text-muted-foreground transition-colors hover:text-foreground"
      >
        {t.auth.withoutAccount}
      </Link>
    </div>
  );
}
