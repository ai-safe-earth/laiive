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
  promoter: null as unknown,
}));

vi.mock("@/api/organizations", () => ({
  useMyOrgs: () => ({ data: data.orgs, isLoading: false }),
  useOrgClaims: () => ({ data: data.claims }),
  useOrgEvents: () => ({ data: data.events }),
  useRoster: () => ({ data: data.roster }),
  useEntitySearch: () => ({ data: data.hits, isFetching: false }),
  useCreateOrg: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateOrg: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCreateClaim: () => ({ mutate: vi.fn(), isPending: false }),
  useWithdrawClaim: () => ({ mutate: vi.fn() }),
}));
vi.mock("@/api/profile", () => ({ usePromoterProfile: () => ({ data: data.promoter }) }));

const OWNED = {
  id: "org-1",
  kind: "venue",
  display_name: "Razzmatazz",
  website: null,
  phone: null,
  contact_email: null,
  role: "owner",
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
  data.promoter = null;
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

  it("sends a signed-out visitor to the promoter door", () => {
    auth.state = { user: null, role: "user", isLoading: false };
    const { container } = renderPage();
    expect(container).toBeEmptyDOMElement();
  });
});
