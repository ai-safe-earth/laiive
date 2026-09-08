import type { ArtistHit, VenueHit } from "@shared/protocol";
import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import {
  useCreateClaim,
  useEntitySearch,
  useMyOrgs,
  useOrgClaims,
  useOrgEvents,
  useRoster,
  useSetRelation,
  useUpdateOrg,
  useWithdrawClaim,
  type Claim,
  type MemberRelation,
  type OrgKind,
  type OrgMembership,
  type OrgRole,
} from "@/api/organizations";
import { usePromoterProfile } from "@/api/profile";
import { LOOKUP_CHUNK } from "@/api/savedEvents";
import { useAuth } from "@/auth/AuthProvider";
import { claimTarget } from "@/auth/claimTarget";
// Label, Badge and Panel are pro-palette primitives that happen to live under
// admin/: they are built on pro.* and status.* tokens, not on anything
// admin-specific. Reused rather than copied.
import { Badge, Label, Panel } from "@/admin/ui";
import { EventCardView } from "@/components/EventCardView";
import { Icon } from "@/components/Icon";
import { Mark } from "@/components/Mark";
import { OrgIdentity, RelationSelect } from "@/components/OrgIdentity";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useTranslation } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

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

      <main className="mx-auto flex max-w-3xl flex-col gap-7 p-4 sm:p-6">
        {orgsLoading ? null : !org ? (
          <OrgIdentity />
        ) : (
          <>
            {orgs && orgs.length > 1 && (
              <OrgTabs orgs={orgs} currentId={org.id} onPick={setSelectedId} />
            )}
            <Group label={t.org.detailsTitle}>
              <OrgDetails org={org} mayEdit={mayEdit} />
            </Group>
            <Group label={t.org.claimsTitle}>
              <ManagedEntities org={org} mayEdit={mayEdit} />
              <LegacyNames />
            </Group>
            <Group label={t.org.eventsTitle}>
              <PublishedEvents org={org} />
            </Group>
          </>
        )}
      </main>
    </div>
  );
}

/**
 * A titled band of panels.
 *
 * What the organisation IS and what it MANAGES were six sibling panels in one
 * stack, two of them titled "venues and artists you manage" and "manage a
 * venue or an artist" and adjacent — which is the confusion this fixes. The
 * heading and its rule do the separating; there is no fourth pro ground and
 * this does not need one.
 */
function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-bebas text-2xl leading-none tracking-[0.04em] text-pro-fg">{label}</h2>
      <div className="h-px bg-pro-border" />
      {children}
    </section>
  );
}

/**
 * One tab per organization you hold a seat in.
 *
 * ponytail: visual tabs on toggle buttons, not the ARIA tab pattern. Real
 * role="tab" needs a roving tabindex and arrow-key handling, and the "panel"
 * here is the whole page below with no focusable entry point worth moving to.
 * Declaring the role without the keyboard behaviour is worse than not
 * declaring it — a reader announces "tab, 1 of 3" and the arrows do nothing.
 * If anyone adds the roles later, add the roving tabindex in the same edit.
 *
 * Plain <button>: our Button is a pill by construction and a tab is not.
 */
function OrgTabs({
  orgs,
  currentId,
  onPick,
}: {
  orgs: OrgMembership[];
  currentId: string;
  onPick: (id: string) => void;
}) {
  return (
    <div className="-mx-4 flex gap-1 overflow-x-auto border-b border-pro-border px-4 sm:mx-0 sm:px-0">
      {orgs.map((candidate) => {
        const current = candidate.id === currentId;
        return (
          <button
            key={candidate.id}
            type="button"
            aria-pressed={current}
            onClick={() => onPick(candidate.id)}
            className={cn(
              "min-h-11 whitespace-nowrap border-b-2 px-4 text-md transition-colors",
              current
                ? "border-pro-accent text-pro-fg"
                : "border-transparent text-pro-muted hover:text-pro-fg",
            )}
          >
            {candidate.display_name}
          </button>
        );
      })}
    </div>
  );
}

function OrgDetails({ org, mayEdit }: { org: OrgMembership; mayEdit: boolean }) {
  const { user } = useAuth();
  const { t } = useTranslation();
  const update = useUpdateOrg(user?.id);
  const setRelation = useSetRelation(user?.id);

  const [website, setWebsite] = useState(org.website ?? "");
  const [phone, setPhone] = useState(org.phone ?? "");
  const [email, setEmail] = useState(org.contact_email ?? "");
  const [address, setAddress] = useState(org.address ?? "");
  const kindLabel: Record<OrgKind, string> = {
    venue: t.org.kindVenue,
    artist: t.org.kindArtist,
    promoter: t.org.kindPromoter,
    agency: t.org.kindAgency,
  };

  const save = async () => {
    try {
      await update.mutateAsync({
        orgId: org.id,
        patch: {
          address: address.trim() || null,
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

  // Your own seat, saved on change: one field, and a save button under a
  // select is a second click for nothing.
  const describeSeat = async (relation: MemberRelation) => {
    try {
      await setRelation.mutateAsync({ orgId: org.id, relation });
      toast.success(t.org.saved);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.org.saveFailed);
    }
  };

  const field = (label: string, value: string, set: (next: string) => void) => (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      <Input
        tone="pro"
        value={value}
        onChange={(event) => set(event.target.value)}
        disabled={!mayEdit}
      />
    </div>
  );

  return (
    <Panel className="flex flex-col gap-3.5 px-5 py-[18px]">
      <div className="flex items-center justify-between gap-2">
        <span className="font-bebas text-xl tracking-[0.03em] text-pro-fg">
          {org.display_name}
        </span>
        <Badge>{kindLabel[org.kind]}</Badge>
      </div>
      {!mayEdit && <p className="text-sm text-pro-muted">{t.org.readOnlyNote}</p>}

      <div className="grid gap-x-5 gap-y-3.5 sm:grid-cols-2">
        {field(t.org.address, address, setAddress)}
        {field(t.org.website, website, setWebsite)}
        {field(t.org.phone, phone, setPhone)}
        {field(t.org.contactEmail, email, setEmail)}
      </div>
      <p className="text-sm leading-[1.45] text-pro-dim">{t.org.evidenceHint}</p>

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

      <Roster
        org={org}
        onDescribeSeat={describeSeat}
        describing={setRelation.isPending}
      />
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
/** How many of the most recently published events open by default. */
const RECENT_EVENTS = 5;

function PublishedEvents({ org }: { org: OrgMembership }) {
  const { language, t } = useTranslation();
  const { user, role } = useAuth();
  const { data: claims } = useOrgClaims(org.id);
  // useOrgClaims already orders created_at descending, so this is
  // most-recently-published first without a second query.
  const uids = (claims ?? [])
    .filter((claim) => claim.entity_type === "event")
    .map((claim) => claim.entity_uid);

  const [limit, setLimit] = useState(RECENT_EVENTS);
  // ponytail: growing the window refetches all of it, because orgKeys.events
  // is keyed on the uid list. A per-page key, or start_at in Postgres so the
  // list can be ordered and paged there, if an org ever pushes enough to feel
  // it. The step is LOOKUP_CHUNK so one click is exactly one round trip — the
  // retriever refuses more uids than that in a single lookup.
  const shown = uids.slice(0, limit);
  const { data: cards } = useOrgEvents(org.id, shown);

  // Newest night first. A promoter opens this to see what they last put up,
  // and the graph answers in the order the uids were asked for. A card with no
  // date sorts to the end rather than throwing.
  const sorted = [...(cards ?? [])].sort(
    (a, b) => new Date(b.start_at ?? 0).getTime() - new Date(a.start_at ?? 0).getTime(),
  );

  return (
    <Panel className="flex flex-col gap-3 px-5 py-[18px]">
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
      {uids.length > shown.length && (
        <Button
          variant="proNeutral"
          className="self-start"
          onClick={() => setLimit((current) => current + LOOKUP_CHUNK)}
        >
          {t.org.eventsAll(uids.length)}
        </Button>
      )}
    </Panel>
  );
}

/**
 * What the organisation manages, and the way to add to it.
 *
 * One panel, because two adjacent ones titled "venues and artists you manage"
 * and "manage a venue or an artist" is the thing that read as confusing. The
 * picker sits under a rule inside the same frame: same subject, second act.
 */
function ManagedEntities({ org, mayEdit }: { org: OrgMembership; mayEdit: boolean }) {
  return (
    <Panel className="flex flex-col gap-3 px-5 py-[18px]">
      <Claims org={org} mayEdit={mayEdit} />
      {mayEdit && (
        <>
          <div className="h-px bg-pro-border" />
          <ClaimSearch org={org} mayEdit={mayEdit} />
        </>
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
    <div className="flex flex-col gap-3">
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
    </div>
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
    <div className="flex flex-col gap-3">
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
          tone="pro"
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
    </div>
  );
}

function seatLabel(role: OrgRole, t: ReturnType<typeof useTranslation>["t"]) {
  return role === "owner" ? t.org.seatOwner : role === "admin" ? t.org.seatAdmin : t.org.seatMember;
}

/**
 * Who is in the organisation, as a compartment inside its panel rather than a
 * panel of its own — your seat is a fact about this organisation, not a
 * separate subject. The elevated fill needs the border to read as a block:
 * against the card ground it is a three-unit difference, and elsewhere it is
 * the strip's shape that carries it, not the colour.
 */
function Roster({
  org,
  onDescribeSeat,
  describing,
}: {
  org: OrgMembership;
  onDescribeSeat: (relation: MemberRelation) => void;
  describing: boolean;
}) {
  const { user } = useAuth();
  const { t } = useTranslation();
  const { data: seats } = useRoster(org.id);
  const relationLabel: Record<MemberRelation, string> = {
    owner: t.org.relationOwner,
    employee: t.org.relationEmployee,
    freelance: t.org.relationFreelance,
    member: t.org.relationMember,
  };

  return (
    <div className="flex flex-col gap-2.5 rounded-[14px] border border-pro-border bg-pro-elevated px-3.5 py-3">
      <Label>{t.org.rosterTitle}</Label>
      <div className="flex items-center gap-2">
        <span className="text-sm text-pro-dim">{t.org.yourSeat}</span>
        <Badge>{seatLabel(org.role, t)}</Badge>
        <RelationSelect
          value={org.relation ?? ""}
          onChange={onDescribeSeat}
          disabled={describing}
        />
      </div>
      <ul className="flex flex-col gap-2">
        {(seats ?? []).map((seat) => {
          const mine = seat.user_id === user?.id;
          // Your own row falls back to the email, which useAuth already has;
          // profiles has no email column. Anyone else falls back to the uid,
          // which is what every seat showed before migration 25 — so a stack
          // without that policy looks exactly like it used to.
          const name = seat.display_name || (mine ? user?.email : null);
          return (
            <li key={seat.user_id} className="flex items-center gap-2">
              <span
                className={cn(
                  "min-w-0 flex-1 truncate text-sm",
                  mine ? "text-pro-fg" : "text-pro-muted",
                  !name && "font-mono",
                )}
              >
                {name || seat.user_id}
              </span>
              {seat.relation && (
                <span className="text-sm text-pro-dim">{relationLabel[seat.relation]}</span>
              )}
              <Badge>{seatLabel(seat.role, t)}</Badge>
            </li>
          );
        })}
      </ul>
      <p className="text-sm text-pro-muted">{t.org.rosterNote}</p>
    </div>
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
