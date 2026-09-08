import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProOrg from "./ProOrg";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

const en = translations.en;

const auth = vi.hoisted(() => ({
  state: { user: { id: "u1" } as { id: string } | null, role: "pro", isLoading: false },
}));
vi.mock("@/auth/AuthProvider", () => ({ useAuth: () => auth.state }));

// The whole data layer is stubbed: this spec is about which panels the screen
// decides to draw, and the queries themselves are covered in
// organizations.test.ts and the gateway's claims.test.ts.
const data = vi.hoisted(() => ({
  orgs: [] as unknown[],
  claims: [] as unknown[],
  roster: [] as unknown[],
  hits: [] as unknown[],
  events: [] as unknown[],
  /** The uids the page last asked for — the window, not the fixture. */
  requested: [] as string[],
  promoter: null as unknown,
  invitations: [] as unknown[],
  create: vi.fn(),
  setRelation: vi.fn(),
  invite: vi.fn(),
  revoke: vi.fn(),
}));

vi.mock("@/api/organizations", () => ({
  useMyOrgs: () => ({ data: data.orgs, isLoading: false }),
  useOrgClaims: () => ({ data: data.claims }),
  useOrgEvents: (_orgId: string, uids: string[]) => {
    // Record the window: what the page chose to ask for is the behaviour under
    // test, and a mock that ignores its argument would pass either way.
    data.requested = uids;
    return { data: data.events };
  },
  useRoster: () => ({ data: data.roster }),
  useEntitySearch: () => ({ data: data.hits, isFetching: false }),
  useCreateOrg: () => ({ mutateAsync: data.create, isPending: false }),
  useUpdateOrg: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSetRelation: () => ({ mutateAsync: data.setRelation, isPending: false }),
  useCreateClaim: () => ({ mutate: vi.fn(), isPending: false }),
  useWithdrawClaim: () => ({ mutate: vi.fn() }),
  usePendingInvitations: () => ({ data: data.invitations }),
  useInvite: () => ({ mutate: data.invite, isPending: false }),
  useRevokeInvitation: () => ({ mutate: data.revoke, isPending: false }),
}));
vi.mock("@/api/profile", () => ({
  usePromoterProfile: () => ({ data: data.promoter }),
}));
// The identity step is the pro grant too; the founding itself is covered in
// OrgIdentity.test.tsx. Here it only has to not dial out.
vi.mock("@/auth/becomePromoter", () => ({ becomePromoter: vi.fn() }));

const OWNED = {
  id: "org-1",
  kind: "venue",
  display_name: "Razzmatazz",
  address: null,
  website: null,
  phone: null,
  contact_email: null,
  role: "owner",
  relation: null,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <LanguageProvider>
        <ProOrg />
      </LanguageProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  auth.state = { user: { id: "u1" }, role: "pro", isLoading: false };
  data.orgs = [];
  data.claims = [];
  data.roster = [];
  data.hits = [];
  data.events = [];
  data.requested = [];
  data.promoter = null;
  data.invitations = [];
  data.create.mockReset().mockResolvedValue("org-1");
  data.setRelation.mockReset().mockResolvedValue(undefined);
  data.invite.mockReset();
  data.revoke.mockReset();
});

describe("/pro/org", () => {
  it("opens on the create form when the promoter belongs to nothing", () => {
    renderPage();
    expect(screen.getByText(en.org.noneTitle)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: en.org.create })).toBeInTheDocument();
    // Nothing to claim for yet, so the picker is not offered.
    expect(screen.queryByText(en.org.searchTitle)).not.toBeInTheDocument();
  });

  it("seeds the first organisation's name from the old promoter profile", () => {
    // A promoter who typed their name into the old free-text profile should
    // not have to type it again to get an organisation.
    data.promoter = { org_name: "Sala Apolo", managed_venues: [], managed_artists: [] };
    renderPage();
    expect(screen.getByPlaceholderText(en.org.namePlaceholder)).toHaveValue("Sala Apolo");
  });

  it("lets the seeded name be cleared", async () => {
    // The seed used to be a fallback for an empty box, so deleting the last
    // character put it straight back and the field could not be emptied.
    data.promoter = { org_name: "Sala Apolo", managed_venues: [], managed_artists: [] };
    renderPage();
    const field = screen.getByPlaceholderText(en.org.namePlaceholder);
    await userEvent.clear(field);
    expect(field).toHaveValue("");
    expect(screen.getByRole("button", { name: en.org.create })).toBeDisabled();
  });

  it("founds the organisation with its kind and your part in it", async () => {
    // kind was never asked before: orgs.ts filed every first publish as a
    // promoter, so a band that published first was a promoter for good.
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: en.org.kindArtist }));
    await userEvent.type(screen.getByPlaceholderText(en.org.namePlaceholder), "Ana Beck Quartet");
    await userEvent.selectOptions(screen.getByLabelText(en.org.relation), "member");
    await userEvent.click(screen.getByRole("button", { name: en.org.create }));

    expect(data.create).toHaveBeenCalledWith({
      kind: "artist",
      display_name: "Ana Beck Quartet",
      relation: "member",
      website: null,
    });
  });

  it("will not found an organisation nobody has a part in", async () => {
    renderPage();
    await userEvent.type(screen.getByPlaceholderText(en.org.namePlaceholder), "Razzmatazz");
    expect(screen.getByRole("button", { name: en.org.create })).toBeDisabled();
  });

  it("shows your seat and lets you describe it", async () => {
    data.orgs = [OWNED];
    data.roster = [
      { user_id: "u1", role: "owner", relation: null, created_at: "2026-09-01", display_name: "Oscar" },
      { user_id: "u2", role: "member", relation: null, created_at: "2026-09-02", display_name: "Ada" },
      // Migration 25 not applied, or a member who never set a name: the uid is
      // what the roster showed for everyone before, so it stays the fallback.
      { user_id: "u3", role: "member", relation: null, created_at: "2026-09-03", display_name: null },
    ];
    renderPage();

    // Every seat carries a name now, not just your own.
    expect(screen.getByText("Oscar")).toBeInTheDocument();
    expect(screen.getByText("Ada")).toBeInTheDocument();
    expect(screen.getByText("u3")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText(en.org.relation), "freelance");
    expect(data.setRelation).toHaveBeenCalledWith({ orgId: "org-1", relation: "freelance" });
  });

  it("opens on the recent events and keeps the rest one click away", async () => {
    // The uid list is claim order, which is newest-published first, so the
    // default window is the last five without a second query. Anything beyond
    // that is a button — the retriever refuses more than 50 uids per lookup,
    // so the page size cannot silently become a failed request.
    data.orgs = [OWNED];
    data.claims = Array.from({ length: 8 }, (_, i) => ({
      id: `c${i}`,
      org_id: "org-1",
      entity_type: "event",
      entity_uid: `e${i}`,
      entity_name: `Night ${i}`,
      basis: "created",
      verified: true,
      status: "active",
      created_at: `2026-09-0${i + 1}`,
    }));
    renderPage();

    expect(data.requested).toHaveLength(5);
    await userEvent.click(screen.getByRole("button", { name: en.org.eventsAll(8) }));
    expect(data.requested).toHaveLength(8);
  });

  it("puts what the organisation is, what it manages and its events in three bands", () => {
    // The complaint this page was rebuilt for: six sibling panels in one
    // stack, two of them titled "venues and artists you manage" and "manage a
    // venue or an artist", adjacent. The headings are the separation.
    data.orgs = [OWNED];
    data.roster = [
      { user_id: "u1", role: "owner", relation: null, created_at: "2026-09-01", display_name: "Oscar" },
    ];
    renderPage();

    const bands = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(bands).toEqual([en.org.detailsTitle, en.org.claimsTitle, en.org.eventsTitle]);
    // Your seat is a fact about this organisation, so it sits inside its band
    // rather than in a panel of its own further down the page.
    expect(screen.getByText(en.org.rosterTitle)).toBeInTheDocument();
  });

  it("keeps published events out of the list you manage", () => {
    // The two are different relationships: a venue is claimed and reviewed, an
    // event is yours because you published it. Rendering them in one list put a
    // "stop managing" button next to an event, which reads as unpublishing it.
    data.orgs = [OWNED];
    data.claims = [
      {
        id: "c1",
        org_id: "org-1",
        entity_type: "venue",
        entity_uid: "v1",
        entity_name: "Razzmatazz",
        basis: "claimed",
        verified: true,
        status: "active",
        created_at: "2026-09-01T00:00:00Z",
      },
      {
        id: "c2",
        org_id: "org-1",
        entity_type: "event",
        entity_uid: "e1",
        entity_name: "Techno Night",
        basis: "created",
        verified: true,
        status: "active",
        created_at: "2026-09-01T00:00:00Z",
      },
    ];
    data.events = [
      {
        uid: "e1",
        name: "Techno Night",
        start_at: "2026-10-01T22:00:00+02:00",
        venue: "Razzmatazz",
        city: "Barcelona",
        source: "pro_submission",
        artists: [],
        genres: [],
      },
    ];
    renderPage();

    // The event is on the page as a card, and exactly once - not also as a row
    // in the manage list, where it would carry a withdraw button.
    expect(screen.getByText("Techno Night")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: en.org.withdraw })).toHaveLength(1);
    expect(screen.getByText(en.org.eventsTitle)).toBeInTheDocument();
  });

  it("shows the org, its claims and the picker to an owner", () => {
    data.orgs = [OWNED];
    data.claims = [
      {
        id: "c1",
        org_id: "org-1",
        entity_type: "venue",
        entity_uid: "v1",
        entity_name: "Razzmatazz",
        basis: "claimed",
        verified: false,
        status: "active",
        created_at: "2026-09-01T00:00:00Z",
      },
    ];
    renderPage();

    expect(screen.getByText("Razzmatazz", { selector: "span.font-bebas" })).toBeInTheDocument();
    expect(screen.getByText(en.org.searchTitle)).toBeInTheDocument();
    // An unverified claim reads as in review, never as verified.
    expect(screen.getByText(en.org.pending)).toBeInTheDocument();
    expect(screen.queryByText(en.org.verified)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: en.org.withdraw })).toBeInTheDocument();
  });

  it("shows a verified claim as verified", () => {
    data.orgs = [OWNED];
    data.claims = [
      {
        id: "c1",
        org_id: "org-1",
        entity_type: "venue",
        entity_uid: "v1",
        entity_name: "Razzmatazz",
        basis: "created",
        verified: true,
        status: "active",
        created_at: "2026-09-01T00:00:00Z",
      },
    ];
    renderPage();
    expect(screen.getByText(en.org.verified)).toBeInTheDocument();
    expect(screen.queryByText(en.org.pending)).not.toBeInTheDocument();
  });

  it("gives a plain member no way to claim or withdraw", () => {
    // The gateway refuses a member seat anyway; the screen should not offer
    // a button whose only outcome is a 403.
    data.orgs = [{ ...OWNED, role: "member" }];
    data.claims = [
      {
        id: "c1",
        org_id: "org-1",
        entity_type: "venue",
        entity_uid: "v1",
        entity_name: "Razzmatazz",
        basis: "claimed",
        verified: false,
        status: "active",
        created_at: "2026-09-01T00:00:00Z",
      },
    ];
    renderPage();

    expect(screen.getByText(en.org.readOnlyNote)).toBeInTheDocument();
    expect(screen.queryByText(en.org.searchTitle)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: en.org.withdraw })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: en.org.save })).not.toBeInTheDocument();
  });

  it("renders the old free-text names as history, not as claims", () => {
    data.orgs = [OWNED];
    data.promoter = {
      org_name: "Razzmatazz",
      managed_venues: ["Sala Clamores"],
      managed_artists: ["Ana Beck Quartet"],
    };
    renderPage();

    expect(screen.getByText(en.org.legacyTitle)).toBeInTheDocument();
    expect(screen.getByText("Sala Clamores")).toBeInTheDocument();
    expect(screen.getByText("Ana Beck Quartet")).toBeInTheDocument();
    // They are not claimable in place: a name is not a uid.
    expect(screen.queryByRole("button", { name: en.org.claim })).not.toBeInTheDocument();
  });

  it("offers the invite control to an admin, with no way to grant ownership", () => {
    data.orgs = [OWNED];
    renderPage();

    expect(screen.getByText(en.org.inviteTitle)).toBeInTheDocument();
    expect(screen.getByLabelText(en.org.inviteEmail)).toBeInTheDocument();
    // member and admin only. Handing an organisation over by link is a
    // different act, and the gateway refuses `owner` too.
    const roles = screen.getByRole("combobox", { name: en.org.rosterTitle });
    const offered = Array.from(roles.querySelectorAll("option")).map((o) => o.textContent);
    expect(offered).toEqual([en.org.seatMember, en.org.seatAdmin]);
  });

  it("hides the invite control from a plain member seat", () => {
    // "admins read invitations" would give them an empty list anyway, and the
    // gateway 403s the POST: a control whose only outcome is a refusal.
    data.orgs = [{ ...OWNED, role: "member" }];
    renderPage();
    expect(screen.queryByText(en.org.inviteTitle)).not.toBeInTheDocument();
  });

  it("asks for the typed address and the chosen seat", async () => {
    data.orgs = [OWNED];
    renderPage();

    await userEvent.type(screen.getByLabelText(en.org.inviteEmail), "ana@sala.cat");
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: en.org.rosterTitle }),
      "admin",
    );
    await userEvent.click(screen.getByRole("button", { name: en.org.inviteSend }));

    expect(data.invite).toHaveBeenCalledWith(
      { email: "ana@sala.cat", role: "admin" },
      expect.anything(),
    );
  });

  it("will not send an empty address", () => {
    data.orgs = [OWNED];
    renderPage();
    expect(screen.getByRole("button", { name: en.org.inviteSend })).toBeDisabled();
  });

  it("lists what is still pending, and revokes by id", async () => {
    data.orgs = [OWNED];
    data.invitations = [
      {
        id: "inv-1",
        email: "ana@sala.cat",
        role: "member",
        expires_at: "2026-09-22T00:00:00Z",
        created_at: "2026-09-08T00:00:00Z",
      },
    ];
    renderPage();

    expect(screen.getByText(en.org.invitePending)).toBeInTheDocument();
    expect(screen.getByText("ana@sala.cat")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: en.org.inviteRevoke }));
    expect(data.revoke).toHaveBeenCalledWith("inv-1", expect.anything());
  });

  it("says nothing about pending invitations when there are none", () => {
    data.orgs = [OWNED];
    renderPage();
    expect(screen.queryByText(en.org.invitePending)).not.toBeInTheDocument();
  });

  it("sends a signed-out visitor to the promoter door", () => {
    auth.state = { user: null, role: "user", isLoading: false };
    const { container } = renderPage();
    expect(container).toBeEmptyDOMElement();
  });
});
