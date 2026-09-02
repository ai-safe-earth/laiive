import type { ArtistHit, VenueHit } from "@shared/protocol";
import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import {
  useCreateClaim,
  useCreateOrg,
  useEntitySearch,
  useMyOrgs,
  useOrgClaims,
  useOrgEvents,
  useRoster,
  useUpdateOrg,
  useWithdrawClaim,
  type Claim,
  type OrgKind,
  type OrgMembership,
} from "@/api/organizations";
import { usePromoterProfile } from "@/api/profile";
import { useAuth } from "@/auth/AuthProvider";
import { claimTarget } from "@/auth/claimTarget";
// Label, Badge and Panel are pro-palette primitives that happen to live under
// admin/: they are built on pro.* and status.* tokens, not on anything
// admin-specific. Reused rather than copied.
import { Badge, Label, Panel } from "@/admin/ui";
import { EventCardView } from "@/components/EventCardView";
import { Icon } from "@/components/Icon";
import { Mark } from "@/components/Mark";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useTranslation } from "@/i18n/useTranslation";

const KINDS: OrgKind[] = ["venue", "artist", "promoter"];

/** A claim's two review states. `created` rows are verified by construction. */
function ClaimBadge({ claim }: { claim: Claim }) {
  const { t } = useTranslation();
  return claim.verified ? (
    <Badge tone="good">{t.org.verified}</Badge>
  ) : (
    <Badge tone="waiting">{t.org.pending}</Badge>
  );
}

export default function ProOrg() {
  const { user, role, isLoading } = useAuth();
  const { t } = useTranslation();

  const { data: orgs, isLoading: orgsLoading } = useMyOrgs(user?.id);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const org: OrgMembership | undefined =
    orgs?.find((candidate) => candidate.id === selectedId) ?? orgs?.[0];
  const mayEdit = org?.role === "owner" || org?.role === "admin";

  if (isLoading) return null;
  // The pro floor is enforced again in create_organization and in every claim
  // route; this only decides which screen to draw.
  if (!user) return <Navigate to="/auth?kind=pro" replace />;
  if (role !== "pro" && role !== "admin") return <Navigate to="/pro" replace />;

  return (
    <div className="min-h-[100dvh] bg-pro-bg">
      <header className="flex items-center gap-3 border-b border-pro-border px-4 py-3 sm:px-6">
        <Link
          to="/pro"
          aria-label={t.org.back}
          className="flex h-11 w-11 items-center justify-center text-pro-dim transition-colors hover:text-pro-fg"
        >
          <Icon name="back" />
        </Link>
        <Mark size={24} />
        <span className="font-mono text-2xs uppercase tracking-[0.11em] text-pro-dim">
          {t.org.title}
        </span>
      </header>

      <main className="mx-auto flex max-w-3xl flex-col gap-4 p-4 sm:p-6">
        {orgsLoading ? null : !org ? (
          <CreateOrg />
        ) : (
          <>
            {orgs && orgs.length > 1 && (
              <div className="flex flex-wrap gap-2">
                {orgs.map((candidate) => (
                  <Button
                    key={candidate.id}
                    variant={candidate.id === org.id ? "cyan" : "proNeutral"}
                    onClick={() => setSelectedId(candidate.id)}
                  >
                    {candidate.display_name}
                  </Button>
                ))}
              </div>
            )}
            <OrgDetails org={org} mayEdit={mayEdit} />
            <PublishedEvents org={org} />
            <Claims org={org} mayEdit={mayEdit} />
            <ClaimSearch org={org} mayEdit={mayEdit} />
            <Roster org={org} />
            <LegacyNames />
          </>
        )}
      </main>
    </div>
  );
}

/** The empty state: a pro account that belongs to no organization yet. */
function CreateOrg() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const create = useCreateOrg(user?.id);
  const { data: promoter } = usePromoterProfile(user?.id);

  const [kind, setKind] = useState<OrgKind>("promoter");
  // Seeded from the old free-text profile so the first org is one keystroke,
  // not a retype. It is a default, not a migration: the name is still theirs.
  //
  // `null` means untouched, and it is the whole reason this is not a plain
  // string. Falling back whenever the box read empty made the seed reappear on
  // deleting the last character, so the name could not be cleared at all.
  const [name, setName] = useState<string | null>(null);
  const seeded = promoter?.org_name ?? "";
  const shown = name ?? seeded;

  const submit = async () => {
    const displayName = shown.trim();
    if (!displayName) return;
    try {
      await create.mutateAsync({ kind, display_name: displayName });
      toast.success(t.org.saved);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.org.saveFailed);
    }
  };

  return (
    <Panel className="flex flex-col gap-3.5 px-5 py-[18px]">
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
              {option === "venue"
                ? t.org.kindVenue
                : option === "artist"
                  ? t.org.kindArtist
                  : t.org.kindPromoter}
            </Button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>{t.org.name}</Label>
        <Input
          value={shown}
          onChange={(event) => setName(event.target.value)}
          placeholder={t.org.namePlaceholder}
          className="border-pro-border bg-pro-control text-pro-fg placeholder:text-pro-dim"
        />
      </div>

      <Button
        variant="cream"
        className="self-start"
        onClick={() => void submit()}
        disabled={create.isPending || !shown.trim()}
      >
        {t.org.create}
      </Button>
    </Panel>
  );
}

function OrgDetails({ org, mayEdit }: { org: OrgMembership; mayEdit: boolean }) {
  const { user } = useAuth();
  const { t } = useTranslation();
  const update = useUpdateOrg(user?.id);

  const [website, setWebsite] = useState(org.website ?? "");
  const [phone, setPhone] = useState(org.phone ?? "");
  const [email, setEmail] = useState(org.contact_email ?? "");

  const save = async () => {
    try {
      await update.mutateAsync({
        orgId: org.id,
        patch: {
          website: website.trim() || null,
          phone: phone.trim() || null,
          contact_email: email.trim() || null,
        },
      });
      toast.success(t.org.saved);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.org.saveFailed);
    }
  };

  const field = (label: string, value: string, set: (next: string) => void) => (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      <Input
        value={value}
        onChange={(event) => set(event.target.value)}
        disabled={!mayEdit}
        className="border-pro-border bg-pro-control text-pro-fg placeholder:text-pro-dim"
      />
    </div>
  );

  return (
    <Panel className="flex flex-col gap-3.5 px-5 py-[18px]">
      <div className="flex items-center justify-between gap-2">
        <span className="font-bebas text-xl tracking-[0.03em] text-pro-fg">
          {org.display_name}
        </span>
        <Badge>{org.kind}</Badge>
      </div>
      {!mayEdit && <p className="text-sm text-pro-muted">{t.org.readOnlyNote}</p>}

      <div className="grid gap-x-5 gap-y-3.5 sm:grid-cols-2">
        {field(t.org.website, website, setWebsite)}
        {field(t.org.phone, phone, setPhone)}
        {field(t.org.contactEmail, email, setEmail)}
      </div>

      {mayEdit && (
        <Button
          variant="cream"
          className="self-start"
          onClick={() => void save()}
          disabled={update.isPending}
        >
          {t.org.save}
        </Button>
      )}
    </Panel>
  );
}

/**
 * The events this organisation published, as real cards.
 *
 * Ownership of an event is recorded by the publish route, never by the picker
 * below — you own what you publish, so there is nothing here to add or
 * withdraw. That is why this is its own panel: mixing it into the list of
 * venues and artists put a "stop managing" button next to an event, which read
 * as a way to unpublish it.
 *
 * The rows carry only a denormalized name, so the uids are exchanged for cards
 * through the same read path /saved uses.
 */
function PublishedEvents({ org }: { org: OrgMembership }) {
  const { language, t } = useTranslation();
  const { user, role } = useAuth();
  const { data: claims } = useOrgClaims(org.id);
  const uids = (claims ?? [])
    .filter((claim) => claim.entity_type === "event")
    .map((claim) => claim.entity_uid);

  const { data: cards } = useOrgEvents(org.id, uids);

  // Soonest first: a promoter opens this to check what is coming, and the graph
  // answers in the order the uids were asked for, which is claim order. A card
  // with no date sorts to the front rather than throwing.
  const sorted = [...(cards ?? [])].sort(
    (a, b) => new Date(a.start_at ?? 0).getTime() - new Date(b.start_at ?? 0).getTime(),
  );

  return (
    <Panel className="flex flex-col gap-3 px-5 py-[18px]">
      <Label>{t.org.eventsTitle}</Label>
      {!uids.length ? (
        <p className="text-sm text-pro-muted">{t.org.eventsNone}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {sorted.map((card) => (
            <li key={card.uid}>
              {/* No save control: this is the promoter's own listing, not a
                  night they are deciding whether to attend. `claimTo` is inert
                  for a pro_submission card - the invitation only renders for a
                  listing that came from the web sweep. */}
              <EventCardView
                card={card}
                language={language}
                claimTo={claimTarget(Boolean(user), role)}
              />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Claims({ org, mayEdit }: { org: OrgMembership; mayEdit: boolean }) {
  const { t } = useTranslation();
  const { data: claims } = useOrgClaims(org.id);
  const withdraw = useWithdrawClaim(org.id);
  // Events live in their own panel above: they arrive by publishing, and the
  // withdraw button below does not apply to them.
  const managed = (claims ?? []).filter((claim) => claim.entity_type !== "event");

  return (
    <Panel className="flex flex-col gap-3 px-5 py-[18px]">
      <Label>{t.org.claimsTitle}</Label>
      {!managed.length ? (
        <p className="text-sm text-pro-muted">{t.org.claimsNone}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {managed.map((claim) => (
            <li
              key={claim.id}
              className="flex flex-wrap items-center gap-2 rounded-[14px] bg-pro-elevated px-3 py-2.5"
            >
              <span className="min-w-0 flex-1 truncate text-md text-pro-fg">
                {claim.entity_name ?? claim.entity_uid}
              </span>
              <Badge>{claim.entity_type}</Badge>
              <ClaimBadge claim={claim} />
              {mayEdit && (
                <Button
                  variant="proNeutral"
                  onClick={() => {
                    withdraw.mutate(claim.id, {
                      onSuccess: () => toast.success(t.org.withdrawn),
                      onError: () => toast.error(t.org.claimFailed),
                    });
                  }}
                >
                  {t.org.withdraw}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function ClaimSearch({ org, mayEdit }: { org: OrgMembership; mayEdit: boolean }) {
  const { t } = useTranslation();
  const [type, setType] = useState<"venue" | "artist">("venue");
  const [draft, setDraft] = useState("");
  // Searching on submit rather than on keystroke: each search is a gateway
  // round trip to the graph, and a picker that fires per character spends
  // dozens of them to answer one question.
  const [query, setQuery] = useState("");
  const { data: hits, isFetching } = useEntitySearch(type, query);
  const claim = useCreateClaim(org.id);

  if (!mayEdit) return null;

  const submitClaim = (uid: string, name: string) => {
    claim.mutate(
      { org_id: org.id, entity_type: type, entity_uid: uid },
      {
        onSuccess: () => toast.success(t.org.claimDone(name)),
        onError: (error) => {
          if (error instanceof ApiError && error.status === 409) {
            toast.error(t.org.claimConflict);
          } else if (error instanceof ApiError && error.status === 404) {
            toast.error(t.org.claimMissing);
          } else {
            toast.error(t.org.claimFailed);
          }
        },
      },
    );
  };

  return (
    <Panel className="flex flex-col gap-3 px-5 py-[18px]">
      <Label>{t.org.searchTitle}</Label>
      <p className="text-sm leading-[1.5] text-pro-muted">{t.org.searchNote}</p>

      <div className="flex flex-wrap gap-2">
        <Button
          variant={type === "venue" ? "cyan" : "proNeutral"}
          onClick={() => setType("venue")}
        >
          {t.org.kindVenue}
        </Button>
        <Button
          variant={type === "artist" ? "cyan" : "proNeutral"}
          onClick={() => setType("artist")}
        >
          {t.org.kindArtist}
        </Button>
      </div>

      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(draft);
        }}
      >
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={t.org.searchPlaceholder}
          aria-label={t.org.searchPlaceholder}
          className="border-pro-border bg-pro-control text-pro-fg placeholder:text-pro-dim"
        />
        <Button variant="cyan" type="submit" disabled={draft.trim().length < 2}>
          {t.org.legacySearch}
        </Button>
      </form>

      {query.trim().length >= 2 && !isFetching && !hits?.length && (
        <p className="text-sm text-pro-muted">{t.org.searchNone}</p>
      )}

      {Boolean(hits?.length) && (
        <ul className="flex flex-col gap-2">
          {hits!.map((hit) => (
            <li
              key={hit.uid}
              className="flex flex-wrap items-center gap-2 rounded-[14px] bg-pro-elevated px-3 py-2.5"
            >
              <span className="min-w-0 flex-1 truncate text-md text-pro-fg">{hit.name}</span>
              <span className="truncate text-sm text-pro-dim">
                {"city" in hit ? ((hit as VenueHit).city ?? "") : (hit as ArtistHit).genres.join(", ")}
              </span>
              <Button
                variant="cyan"
                onClick={() => submitClaim(hit.uid, hit.name)}
                disabled={claim.isPending}
              >
                {t.org.claim}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Roster({ org }: { org: OrgMembership }) {
  const { t } = useTranslation();
  const { data: seats } = useRoster(org.id);
  const seatLabel = (role: string) =>
    role === "owner" ? t.org.seatOwner : role === "admin" ? t.org.seatAdmin : t.org.seatMember;

  return (
    <Panel className="flex flex-col gap-3 px-5 py-[18px]">
      <Label>{t.org.rosterTitle}</Label>
      <ul className="flex flex-col gap-2">
        {(seats ?? []).map((seat) => (
          <li key={seat.user_id} className="flex items-center gap-2">
            <span className="min-w-0 flex-1 truncate font-mono text-sm text-pro-muted">
              {seat.user_id}
            </span>
            <Badge>{seatLabel(seat.role)}</Badge>
          </li>
        ))}
      </ul>
      <p className="text-sm text-pro-muted">{t.org.rosterNote}</p>
    </Panel>
  );
}

/**
 * The free-text venue and artist names from the old promoter profile.
 *
 * Rendered once, as history rather than as claims, and deliberately not
 * auto-migrated: a name is not a uid, and matching "Apolo" to the right room
 * needs a human eye. Each one is a prompt to search and claim it properly.
 */
function LegacyNames() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const { data: promoter } = usePromoterProfile(user?.id);
  const names = [...(promoter?.managed_venues ?? []), ...(promoter?.managed_artists ?? [])];
  if (!names.length) return null;

  return (
    <Panel className="flex flex-col gap-3 px-5 py-[18px]">
      <Label>{t.org.legacyTitle}</Label>
      <p className="text-sm leading-[1.5] text-pro-muted">{t.org.legacyNote}</p>
      <ul className="flex flex-wrap gap-2">
        {names.map((name) => (
          <li
            key={name}
            className="rounded-full border border-pro-border bg-pro-elevated px-3 py-[7px] text-sm text-pro-muted"
          >
            {name}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
