import { ArrowLeft, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { toast } from "sonner";
import {
  usePromoterProfile,
  useProfile,
  useSavePromoterProfile,
  useUpdateProfile,
} from "@/api/profile";
import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useLanguagePreference } from "@/i18n/useLanguagePreference";
import { LANGUAGES, type Language } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

const LANGUAGE_LABELS: Record<Language, string> = {
  en: "english",
  es: "español",
  it: "italiano",
  ca: "català",
};

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
  const [draft, setDraft] = useState("");

  const add = () => {
    const value = draft.trim();
    if (!value || items.includes(value)) return setDraft("");
    onChange([...items, value]);
    setDraft("");
  };

  return (
    <div className="space-y-2">
      <label className="font-ibm-plex text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </label>
      {items.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {items.map((item) => (
            <li
              key={item}
              className="flex items-center gap-1 rounded-full border border-border bg-muted px-3 py-1 text-sm"
            >
              {item}
              <button
                type="button"
                aria-label={`remove ${item}`}
                onClick={() => onChange(items.filter((i) => i !== item))}
                className="text-muted-foreground hover:text-destructive"
              >
                <X className="h-3 w-3" />
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
        <Button variant="outline" onClick={add} disabled={!draft.trim()}>
          add
        </Button>
      </div>
    </div>
  );
}

export default function Account() {
  const { user, role, isLoading: authLoading } = useAuth();
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
      toast.success("profile saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "could not save the profile");
    }
  };

  const savePromoterProfile = async () => {
    if (!orgName.trim()) return toast.error("the organisation name is required");
    try {
      await savePromoter.mutateAsync({
        org_name: orgName.trim(),
        website: website.trim() || null,
        phone: phone.trim() || null,
        managed_venues: venues,
        managed_artists: artists,
        notes: promoter?.notes ?? null,
      });
      toast.success("promoter details saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "could not save the details");
    }
  };

  return (
    <div className="min-h-[100dvh] bg-background">
      <header className="flex items-center gap-3 border-b border-border px-4 py-3">
        <Link
          to="/"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-primary"
        >
          <ArrowLeft className="h-4 w-4" /> back
        </Link>
        <h1 className="font-montserrat text-lg font-bold text-foreground">account</h1>
      </header>

      <div className="mx-auto max-w-xl space-y-8 p-4 sm:p-6">
        <section className="space-y-4 rounded-lg border border-border bg-card p-5">
          <div>
            <h2 className="font-montserrat text-base font-bold text-foreground">you</h2>
            <p className="text-xs text-muted-foreground">
              {user?.email} · <span className="uppercase text-accent">{role}</span>
            </p>
          </div>

          <div className="space-y-2">
            <label
              htmlFor="display-name"
              className="font-ibm-plex text-xs uppercase tracking-wider text-muted-foreground"
            >
              display name
            </label>
            <Input
              id="display-name"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder={profileLoading ? "…" : "how we greet you"}
              autoComplete="nickname"
            />
          </div>

          <div className="space-y-2">
            <span className="font-ibm-plex text-xs uppercase tracking-wider text-muted-foreground">
              language
            </span>
            <div className="flex flex-wrap gap-2">
              {LANGUAGES.map((code) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => chooseLanguage(code)}
                  className={cn(
                    "rounded-md border px-3 py-1.5 font-ibm-plex text-sm transition-colors",
                    code === language
                      ? "border-primary text-primary"
                      : "border-border text-muted-foreground hover:text-foreground",
                  )}
                >
                  {LANGUAGE_LABELS[code]}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Saved to your account — the assistant still answers in whatever language you
              write in.
            </p>
          </div>

          <Button onClick={saveProfile} disabled={updateProfile.isPending}>
            {updateProfile.isPending ? "…" : "save"}
          </Button>
        </section>

        {isPro && (
          <section className="space-y-4 rounded-lg border border-border bg-card p-5">
            <div>
              <h2 className="font-montserrat text-base font-bold text-foreground">
                promoter
              </h2>
              <p className="text-xs text-muted-foreground">
                What you run. Submitted events are linked to you regardless; this is
                context, not a permission.
              </p>
            </div>

            <div className="space-y-2">
              <label
                htmlFor="org-name"
                className="font-ibm-plex text-xs uppercase tracking-wider text-muted-foreground"
              >
                organisation
              </label>
              <Input
                id="org-name"
                value={orgName}
                onChange={(event) => setOrgName(event.target.value)}
                placeholder={promoterLoading ? "…" : "venue, label, collective…"}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label
                  htmlFor="website"
                  className="font-ibm-plex text-xs uppercase tracking-wider text-muted-foreground"
                >
                  website
                </label>
                <Input
                  id="website"
                  type="url"
                  value={website}
                  onChange={(event) => setWebsite(event.target.value)}
                  placeholder="https://"
                />
              </div>
              <div className="space-y-2">
                <label
                  htmlFor="phone"
                  className="font-ibm-plex text-xs uppercase tracking-wider text-muted-foreground"
                >
                  phone
                </label>
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
              label="venues you manage"
              items={venues}
              onChange={setVenues}
              placeholder="Sala Clamores"
            />
            <ChipList
              label="artists you manage"
              items={artists}
              onChange={setArtists}
              placeholder="Ana Beck Quartet"
            />

            <Button onClick={savePromoterProfile} disabled={savePromoter.isPending}>
              {savePromoter.isPending ? "…" : "save"}
            </Button>
          </section>
        )}
      </div>
    </div>
  );
}
