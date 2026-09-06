import { useState } from "react";
import { toast } from "sonner";
import { useCreateOrg, type MemberRelation, type OrgKind } from "@/api/organizations";
import { usePromoterProfile } from "@/api/profile";
import { useAuth } from "@/auth/AuthProvider";
import { becomePromoter } from "@/auth/becomePromoter";
// Pro-palette primitives that happen to live under admin/ — see ProOrg.tsx.
import { Label, Panel } from "@/admin/ui";
import { Button } from "@/components/ui/Button";
import { Input, PRO_FIELD } from "@/components/ui/Input";
import { useTranslation } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

const KINDS: OrgKind[] = ["venue", "artist", "promoter", "agency"];
const RELATIONS: MemberRelation[] = ["owner", "employee", "freelance", "member"];

/** Native select in the pro skin; shared with /pro/org, where the seat is edited later. */
export function RelationSelect({
  value,
  onChange,
  disabled,
}: {
  value: MemberRelation | "";
  onChange: (next: MemberRelation) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const label: Record<MemberRelation, string> = {
    owner: t.org.relationOwner,
    employee: t.org.relationEmployee,
    freelance: t.org.relationFreelance,
    member: t.org.relationMember,
  };
  return (
    <select
      required
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value as MemberRelation)}
      aria-label={t.org.relation}
      className={cn(
        "h-11 w-full rounded-full border px-4 text-base [color-scheme:dark]",
        "focus-visible:outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-50",
        PRO_FIELD,
        !value && "text-pro-dim",
      )}
    >
      <option value="" disabled>
        {t.org.relationPlaceholder}
      </option>
      {RELATIONS.map((option) => (
        <option key={option} value={option}>
          {label[option]}
        </option>
      ))}
    </select>
  );
}

/**
 * The one identity question, asked once: what you stand behind (kind), what
 * it is called, and what you are to it. Mounted on /pro the first time a
 * signed-in account opens it and on /pro/org's empty state — the same form,
 * so the answer is typed exactly once.
 *
 * It is also the door for an account that is not a promoter yet: writing the
 * promoter_profiles row is the grant (becomePromoter), and the RPC reads
 * user_roles directly, so founding the org right after works before the
 * refreshed JWT lands. The refresh flips useAuth().role, which re-renders
 * whatever gate mounted this; no callback needed.
 */
export function OrgIdentity() {
  const { user, role } = useAuth();
  const { t } = useTranslation();
  const create = useCreateOrg(user?.id);
  const { data: promoter } = usePromoterProfile(user?.id);

  const [kind, setKind] = useState<OrgKind>("promoter");
  const [relation, setRelation] = useState<MemberRelation | "">("");
  const [website, setWebsite] = useState("");
  // Seeded from the free-text profile so the first org is one keystroke, not
  // a retype. `null` means untouched — a plain string fell back to the seed
  // on deleting the last character, so the name could not be cleared.
  const [name, setName] = useState<string | null>(null);
  const shown = name ?? promoter?.org_name ?? "";
  const kindLabel: Record<OrgKind, string> = {
    venue: t.org.kindVenue,
    artist: t.org.kindArtist,
    promoter: t.org.kindPromoter,
    agency: t.org.kindAgency,
  };

  const submit = async () => {
    const displayName = shown.trim();
    if (!user || !displayName || !relation) return;
    const wasPro = role === "pro" || role === "admin";
    try {
      if (!wasPro) await becomePromoter(user.id, displayName);
      await create.mutateAsync({
        kind,
        display_name: displayName,
        relation,
        website: website.trim() || null,
      });
      toast.success(wasPro ? t.org.saved : t.account.becamePromoter);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.org.saveFailed);
    }
  };

  return (
    <Panel className="flex w-full max-w-xl flex-col gap-3.5 px-5 py-[18px]">
      <span className="font-bebas text-xl tracking-[0.03em] text-pro-fg">{t.org.noneTitle}</span>
      <p className="text-sm leading-[1.5] text-pro-muted">{t.org.noneNote}</p>

      <div className="flex flex-col gap-1.5">
        <Label>{t.org.kind}</Label>
        <div className="flex flex-wrap gap-2">
          {KINDS.map((option) => (
            <Button
              key={option}
              variant={option === kind ? "cyan" : "proNeutral"}
              onClick={() => setKind(option)}
            >
              {kindLabel[option]}
            </Button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>{t.org.name}</Label>
        <Input
          tone="pro"
          value={shown}
          onChange={(event) => setName(event.target.value)}
          placeholder={t.org.namePlaceholder}
          autoComplete="organization"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>{t.org.relation}</Label>
        <RelationSelect value={relation} onChange={setRelation} />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>{t.org.website}</Label>
        <Input
          tone="pro"
          type="url"
          value={website}
          onChange={(event) => setWebsite(event.target.value)}
          placeholder="https://"
          autoComplete="url"
        />
        <p className="text-sm leading-[1.45] text-pro-dim">{t.org.evidenceHint}</p>
      </div>

      <Button
        variant="cream"
        className="self-start"
        onClick={() => void submit()}
        disabled={create.isPending || !shown.trim() || !relation}
      >
        {t.org.create}
      </Button>
    </Panel>
  );
}
