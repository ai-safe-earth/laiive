import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { useMyOrgs, useOrgClaims } from "@/api/organizations";
import { useProfile, useUpdateProfile } from "@/api/profile";
import { useAuth } from "@/auth/AuthProvider";
import { Icon } from "@/components/Icon";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useLanguagePreference } from "@/i18n/useLanguagePreference";
import { LANGUAGES, useTranslation, type Language } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

const LANGUAGE_LABELS: Record<Language, string> = {
  en: "english",
  es: "español",
  it: "italiano",
  ca: "català",
};

/** Mono, small caps — the label voice for every setting on this page. */
function Label({
  htmlFor,
  pro,
  children,
}: {
  htmlFor?: string;
  pro: boolean;
  children: React.ReactNode;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className={cn(
        "font-mono text-xs uppercase tracking-[0.11em]",
        pro ? "text-pro-dim" : "text-muted-foreground",
      )}
    >
      {children}
    </label>
  );
}

/**
 * The promoter's organisation, read-only, linking to the screen that owns it.
 * Identity itself — kind, name, your relation to it — is asked on /pro the
 * first time and edited on /pro/org; this page only points there.
 */
function OrgSummary() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const { data: orgs } = useMyOrgs(user?.id);
  const org = orgs?.[0];
  const { data: claims } = useOrgClaims(org?.id);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Label pro>{t.org.summaryTitle}</Label>
      <span className="min-w-0 flex-1 truncate text-md text-pro-fg">
        {org ? org.display_name : t.org.noneTitle}
      </span>
      {org && <span className="text-sm text-pro-muted">{t.org.summary(claims?.length ?? 0)}</span>}
      <Link
        to="/pro/org"
        className="inline-flex min-h-11 items-center text-md text-pro-accent transition-opacity hover:opacity-80"
      >
        {t.org.manage}
      </Link>
    </div>
  );
}

export default function Account() {
  const { user, role, isLoading: authLoading } = useAuth();
  // Back means back. A promoter who came from /pro was being returned to the
  // consumer chat, which is a different product wearing the same header.
  // Router state rather than a query string: it survives no URL, and a deep
  // link or a bookmark simply has none and falls back to the chat.
  const location = useLocation() as { state?: { from?: string } };
  const backTo = location.state?.from ?? "/";
  // Arriving from the promoter side, the page wears the promoter ground: the
  // same settings, not a trip back to the consumer room to change them.
  const pro = backTo.startsWith("/pro");
  const { t } = useTranslation();
  const { language, chooseLanguage } = useLanguagePreference();

  const { data: profile, isLoading: profileLoading } = useProfile(user?.id);
  const updateProfile = useUpdateProfile(user?.id);

  const [displayName, setDisplayName] = useState("");

  // Seed from the server ONCE per account, not on every refetch. react-query
  // hands back a fresh object each time it refetches, and picking a language
  // writes through and invalidates the profile — seeding on that would wipe a
  // display name typed but not yet saved. (It did, before this ref.)
  const seededProfile = useRef<string | null>(null);
  useEffect(() => {
    if (!profile || seededProfile.current === profile.id) return;
    seededProfile.current = profile.id;
    setDisplayName(profile.display_name ?? "");
  }, [profile]);

  if (!authLoading && !user) return <Navigate to="/auth" replace />;

  const isPro = role === "pro" || role === "admin";

  const saveProfile = async () => {
    try {
      await updateProfile.mutateAsync({ display_name: displayName.trim() || null });
      toast.success(t.account.profileSaved);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.account.saveFailed);
    }
  };

  return (
    <div className={cn("min-h-[100dvh]", pro ? "bg-pro-bg" : "bg-background")}>
      <header
        className={cn(
          "flex items-center gap-2 border-b px-3 py-2 sm:px-4",
          pro ? "border-pro-border" : "border-rule",
        )}
      >
        <Link
          to={backTo}
          aria-label={t.account.back}
          className={cn(
            "flex h-11 w-11 items-center justify-center transition-colors",
            pro ? "text-pro-dim hover:text-pro-fg" : "text-ink-dim hover:text-foreground",
          )}
        >
          <Icon name="back" />
        </Link>
        <h1
          className={cn(
            "font-bebas text-3xl leading-none tracking-[0.04em]",
            pro ? "text-pro-fg" : "text-card-foreground",
          )}
        >
          {t.account.title}
        </h1>
      </header>

      <div className="mx-auto flex max-w-xl flex-col gap-6 p-4 sm:p-6">
        <section
          className={cn(
            "flex flex-col gap-4 rounded-[26px] border p-6",
            pro ? "border-pro-border bg-pro-card" : "border-hairline/[0.07] bg-card",
          )}
        >
          <div className="flex flex-col gap-1">
            <h2
              className={cn(
                "font-bebas text-2xl leading-none tracking-[0.04em]",
                pro ? "text-pro-fg" : "text-card-foreground",
              )}
            >
              {t.account.you}
            </h2>
            <p className={cn("font-mono text-xs", pro ? "text-pro-dim" : "text-ink-dim")}>
              {user?.email} · <span className="uppercase tracking-[0.11em]">{role}</span>
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label pro={pro} htmlFor="display-name">
              {t.account.displayName}
            </Label>
            <Input
              id="display-name"
              tone={pro ? "pro" : undefined}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder={profileLoading ? "…" : t.account.displayNamePlaceholder}
              autoComplete="nickname"
            />
          </div>

          {/* Language lives here, in settings — never in a header. */}
          <div className="flex flex-col gap-2">
            <Label pro={pro}>{t.account.language}</Label>
            <div className="flex flex-wrap gap-2">
              {LANGUAGES.map((code) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => chooseLanguage(code)}
                  className={cn(
                    "h-11 rounded-full border px-4 text-md transition-colors",
                    code === language
                      ? pro
                        ? "border-pro-accent text-pro-accent"
                        : "border-primary text-primary"
                      : pro
                        ? "border-pro-border text-pro-muted hover:text-pro-fg"
                        : "border-field-border text-muted-foreground hover:text-foreground",
                  )}
                >
                  {LANGUAGE_LABELS[code]}
                </button>
              ))}
            </div>
            <p className={cn("text-sm leading-[1.45]", pro ? "text-pro-muted" : "text-muted-foreground")}>
              {t.account.languageNote}
            </p>
          </div>

          <Button
            variant={pro ? "cream" : "primary"}
            className="self-start"
            onClick={saveProfile}
            disabled={updateProfile.isPending}
          >
            {updateProfile.isPending ? "…" : t.account.save}
          </Button>
        </section>

        {/* The promoter block wears the promoter ground even inside the
            consumer account screen — same tokens as /pro, so the two read as
            one room and this reads as the door into it. The door itself is
            /pro: it asks who you are the first time, and that grants the role. */}
        <section className="flex flex-col gap-4 rounded-[26px] border border-pro-border bg-pro-card p-6">
          <div className="flex flex-col gap-1">
            <h2 className="font-bebas text-2xl leading-none tracking-[0.04em] text-pro-fg">
              {isPro ? t.account.promoter : t.account.becomePromoter}
            </h2>
            <p className="text-sm leading-[1.45] text-pro-muted">
              {isPro ? t.account.promoterNote : t.account.becomePromoterNote}
            </p>
          </div>

          {isPro ? (
            <OrgSummary />
          ) : (
            <Link
              to="/pro"
              className="inline-flex min-h-11 items-center self-start text-md text-pro-accent transition-opacity hover:opacity-80"
            >
              {t.account.becomePromoterCta}
            </Link>
          )}
        </section>
      </div>
    </div>
  );
}
