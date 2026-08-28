import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import {
  usePromoterProfile,
  useProfile,
  useSavePromoterProfile,
  useUpdateProfile,
} from "@/api/profile";
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
function Label({ htmlFor, children }: { htmlFor?: string; children: React.ReactNode }) {
  return (
    <label
      htmlFor={htmlFor}
      className="font-mono text-xs uppercase tracking-[0.11em] text-muted-foreground"
    >
      {children}
    </label>
  );
}

/** Free-form chip list — the graph owns the real entities, this is what the
 *  promoter says they manage (D8). */
function ChipList({
  label,
  items,
  onChange,
  placeholder,
}: {
  label: string;
  items: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState("");

  const add = () => {
    const value = draft.trim();
    if (!value || items.includes(value)) return setDraft("");
    onChange([...items, value]);
    setDraft("");
  };

  return (
    <div className="flex flex-col gap-2">
      <Label>{label}</Label>
      {items.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {items.map((item) => (
            <li
              key={item}
              className="flex items-center gap-1.5 rounded-full border border-field-border bg-field pl-4 pr-1.5 text-md text-foreground"
            >
              {item}
              <button
                type="button"
                aria-label={t.account.remove(item)}
                onClick={() => onChange(items.filter((i) => i !== item))}
                className="flex h-11 w-11 items-center justify-center rounded-full text-ink-dim transition-colors hover:text-destructive"
              >
                <Icon name="close" className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
        />
        <Button variant="neutral" onClick={add} disabled={!draft.trim()}>
          {t.account.add}
        </Button>
      </div>
    </div>
  );
}

export default function Account() {
  const { user, role, isLoading: authLoading, refreshRole } = useAuth();
  // Back means back. A promoter who came from /pro was being returned to the
  // consumer chat, which is a different product wearing the same header.
  // Router state rather than a query string: it survives no URL, and a deep
  // link or a bookmark simply has none and falls back to the chat.
  const location = useLocation() as { state?: { from?: string } };
  const backTo = location.state?.from ?? "/";
  const { t } = useTranslation();
  const { language, chooseLanguage } = useLanguagePreference();

  const { data: profile, isLoading: profileLoading } = useProfile(user?.id);
  const updateProfile = useUpdateProfile(user?.id);
  const { data: promoter, isLoading: promoterLoading } = usePromoterProfile(user?.id);
  const savePromoter = useSavePromoterProfile(user?.id);

  const [displayName, setDisplayName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [website, setWebsite] = useState("");
  const [phone, setPhone] = useState("");
  const [venues, setVenues] = useState<string[]>([]);
  const [artists, setArtists] = useState<string[]>([]);

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

  const seededPromoter = useRef<string | null>(null);
  useEffect(() => {
    if (!promoter || seededPromoter.current === promoter.user_id) return;
    seededPromoter.current = promoter.user_id;
    setOrgName(promoter.org_name);
    setWebsite(promoter.website ?? "");
    setPhone(promoter.phone ?? "");
    setVenues(promoter.managed_venues);
    setArtists(promoter.managed_artists);
  }, [promoter]);

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

  const savePromoterProfile = async () => {
    if (!orgName.trim()) return toast.error(t.account.orgRequired);
    try {
      await savePromoter.mutateAsync({
        org_name: orgName.trim(),
        website: website.trim() || null,
        phone: phone.trim() || null,
        managed_venues: venues,
        managed_artists: artists,
        notes: promoter?.notes ?? null,
      });
      if (isPro) {
        toast.success(t.account.promoterSaved);
        return;
      }
      // The row just written is what granted the role (see the trigger in
      // 20260820000012). The grant is stamped into the JWT at issue, so without
      // re-minting the token this page — and /pro — would keep reading the old
      // claim and refusing the promoter it just created.
      await refreshRole();
      toast.success(t.account.becamePromoter);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.account.saveFailed);
    }
  };

  return (
    <div className="min-h-[100dvh] bg-background">
      <header className="flex items-center gap-2 border-b border-rule px-3 py-2 sm:px-4">
        <Link
          to={backTo}
          aria-label={t.account.back}
          className="flex h-11 w-11 items-center justify-center text-ink-dim transition-colors hover:text-foreground"
        >
          <Icon name="back" />
        </Link>
        <h1 className="font-bebas text-3xl leading-none tracking-[0.04em] text-card-foreground">
          {t.account.title}
        </h1>
      </header>

      <div className="mx-auto flex max-w-xl flex-col gap-6 p-4 sm:p-6">
        <section className="flex flex-col gap-4 rounded-[26px] border border-hairline/[0.07] bg-card p-6">
          <div className="flex flex-col gap-1">
            <h2 className="font-bebas text-2xl leading-none tracking-[0.04em] text-card-foreground">
              {t.account.you}
            </h2>
            <p className="font-mono text-xs text-ink-dim">
              {user?.email} · <span className="uppercase tracking-[0.11em]">{role}</span>
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="display-name">{t.account.displayName}</Label>
            <Input
              id="display-name"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder={profileLoading ? "…" : t.account.displayNamePlaceholder}
              autoComplete="nickname"
            />
          </div>

          {/* Language lives here, in settings — never in a header. */}
          <div className="flex flex-col gap-2">
            <Label>{t.account.language}</Label>
            <div className="flex flex-wrap gap-2">
              {LANGUAGES.map((code) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => chooseLanguage(code)}
                  className={cn(
                    "h-11 rounded-full border px-4 text-md transition-colors",
                    code === language
                      ? "border-primary text-primary"
                      : "border-field-border text-muted-foreground hover:text-foreground",
                  )}
                >
                  {LANGUAGE_LABELS[code]}
                </button>
              ))}
            </div>
            <p className="text-sm leading-[1.45] text-muted-foreground">
              {t.account.languageNote}
            </p>
          </div>

          <Button className="self-start" onClick={saveProfile} disabled={updateProfile.isPending}>
            {updateProfile.isPending ? "…" : t.account.save}
          </Button>
        </section>

        {/* Open to every signed-in account, not just pros. This form is the one
            way to become a promoter: saving it grants the role. Gating it on
            already having the role is what made /pro's "not a pro account yet →"
            link point at a page that could not help. */}
        {/* The promoter block wears the promoter ground even inside the
            consumer account screen — same tokens as /pro, so the two read as
            one room and this reads as the door into it. */}
        <section className="flex flex-col gap-4 rounded-[26px] border border-pro-border bg-pro-card p-6">
            <div className="flex flex-col gap-1">
              <h2 className="font-bebas text-2xl leading-none tracking-[0.04em] text-pro-fg">
                {isPro ? t.account.promoter : t.account.becomePromoter}
              </h2>
              <p className="text-sm leading-[1.45] text-pro-muted">
                {isPro ? t.account.promoterNote : t.account.becomePromoterNote}
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="org-name">{t.account.organisation}</Label>
              <Input
                id="org-name"
                value={orgName}
                onChange={(event) => setOrgName(event.target.value)}
                placeholder={promoterLoading ? "…" : t.account.organisationPlaceholder}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="website">{t.account.website}</Label>
                <Input
                  id="website"
                  type="url"
                  value={website}
                  onChange={(event) => setWebsite(event.target.value)}
                  placeholder="https://"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="phone">{t.account.phone}</Label>
                <Input
                  id="phone"
                  type="tel"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  placeholder="+34…"
                />
              </div>
            </div>

            <ChipList
              label={t.account.venues}
              items={venues}
              onChange={setVenues}
              placeholder="Sala Clamores"
            />
            <ChipList
              label={t.account.artists}
              items={artists}
              onChange={setArtists}
              placeholder="Ana Beck Quartet"
            />

            <Button
              className="self-start"
              onClick={savePromoterProfile}
              disabled={savePromoter.isPending}
            >
              {savePromoter.isPending ? "…" : isPro ? t.account.save : t.account.becomePromoterCta}
            </Button>
        </section>
      </div>
    </div>
  );
}
