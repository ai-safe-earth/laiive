import type { EventCard } from "@shared/protocol";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { EventCardView } from "./EventCardView";
import { claimTarget } from "@/auth/claimTarget";
import { LanguageProvider } from "@/i18n/useTranslation";

/** The Bergamo gig that started this: 22:00 at the door, 20:00 UTC. */
const BERGAMO: EventCard = {
  uid: "e1",
  name: "BobSin",
  artists: ["BobSin"],
  venue: "train station square",
  city: "Bergamo",
  start_at: "2026-08-22T20:00:00Z",
  timezone: "Europe/Rome",
  start_time_known: true,
  source: "pro_submission",
};

function renderCard(card: EventCard, claimTo = "/auth?kind=pro") {
  // The claim invitation is a router link, so every render needs a router.
  return render(
    <MemoryRouter>
      <LanguageProvider>
        <EventCardView card={card} language="en" claimTo={claimTo} />
      </LanguageProvider>
    </MemoryRouter>,
  );
}

describe("the time a card prints", () => {
  it("shows the hour at the venue, not on the reader's clock", () => {
    // jsdom runs on this machine's zone; the card must ignore it. Read in UTC
    // this is 20:00 on the 22nd, and in New York 16:00 — neither is the answer.
    renderCard(BERGAMO);
    // "en" formats 12-hour: 22:00 in Rome reads as 10:00 PM on the 22nd.
    // \s rather than a literal space: ICU 72+ separates the time from the
    // meridiem with U+202F, a narrow no-break space, and JS \s matches it.
    expect(screen.getByText(/Aug 22, 10:00\sPM/)).toBeTruthy();
  });

  it("keeps a late gig on the day the venue calls it", () => {
    // 23:30 in Barcelona is 21:30 UTC. Printed in UTC the date is right by
    // luck; printed from Tokyo it is the 23rd. The zone is what settles it.
    renderCard({
      ...BERGAMO,
      city: "Barcelona",
      start_at: "2026-08-22T21:30:00Z",
      timezone: "Europe/Madrid",
    });
    expect(screen.getByText(/Aug 22, 11:30\sPM/)).toBeTruthy();
  });

  it("falls back to the reader's clock when the row carries no zone", () => {
    // Rows written before the writer resolved zones. A card with no date at
    // all would be worse than one on the wrong clock.
    const { container } = renderCard({ ...BERGAMO, timezone: null });
    expect(container.textContent).toMatch(/Aug 2[123]/);
  });

  it("does not throw on a zone Intl does not know", () => {
    const { container } = renderCard({ ...BERGAMO, timezone: "Mars/Olympus" });
    expect(container.textContent).toContain("BobSin");
  });

  it("hides the hour when the listing never stated one", () => {
    renderCard({
      ...BERGAMO,
      start_at: "2026-08-22T00:00:00+02:00",
      start_time_known: false,
    });
    expect(screen.queryByText(/AM|PM/)).toBeNull();
    expect(screen.getByText(/Aug 22/)).toBeTruthy();
  });
});

describe("where a card says it came from", () => {
  const WEB: EventCard = {
    ...BERGAMO,
    source: "admin_search",
    source_url: "https://www.ecodibergamo.it/agenda/bobsin",
    source_domain: "ecodibergamo.it",
  };

  it("marks a web-found listing and names the page behind it", async () => {
    const user = userEvent.setup();
    renderCard(WEB);
    // The mark is the affordance; the source is one tap away, not hidden.
    await user.click(screen.getByRole("button", { name: /where did this come from/i }));
    const link = screen.getByRole("link", { name: "ecodibergamo.it" });
    expect(link.getAttribute("href")).toBe(WEB.source_url);
    expect(link.getAttribute("rel")).toContain("noopener");
  });

  it("invites the promoter to take the listing over, and the invitation is a door", async () => {
    const user = userEvent.setup();
    renderCard(WEB);
    await user.click(screen.getByRole("button", { name: /where did this come from/i }));
    const claim = screen.getByRole("link", { name: /promoter account/i });
    // Signed out (no claimTo passed): the promoter sign-up is the default.
    expect(claim.getAttribute("href")).toBe("/auth?kind=pro");
    // The mark's red, on the call to action itself.
    expect(claim.className).toContain("text-mark-unverified");
  });

  it("points the invitation where the page says the reader belongs", async () => {
    const user = userEvent.setup();
    renderCard(WEB, "/pro");
    await user.click(screen.getByRole("button", { name: /where did this come from/i }));
    expect(screen.getByRole("link", { name: /promoter account/i }).getAttribute("href")).toBe(
      "/pro",
    );
  });

  it("marks a promoter submission as confirmed instead", async () => {
    const user = userEvent.setup();
    renderCard(BERGAMO); // source: pro_submission
    expect(screen.queryByRole("button", { name: /where did this come from/i })).toBeNull();
    await user.click(screen.getByRole("button", { name: /who confirmed this/i }));
    expect(screen.getByText(/confirmed by a promoter/i)).toBeTruthy();
  });

  it("still renders a web card whose source was never recorded", async () => {
    // Every admin_search row written before the writer carried the URL.
    const user = userEvent.setup();
    renderCard({ ...WEB, source_url: null, source_domain: null });
    await user.click(screen.getByRole("button", { name: /where did this come from/i }));
    // No source link, since the page was never recorded. The claim door stays.
    expect(screen.queryByRole("link", { name: /ecodibergamo|original listing/i })).toBeNull();
    expect(screen.getByRole("link", { name: /promoter account/i })).toBeTruthy();
  });

  it("gives a seed row neither mark", () => {
    renderCard({ ...BERGAMO, source: "seed" });
    expect(screen.queryByRole("button", { name: /where did this come from/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /who confirmed this/i })).toBeNull();
  });
});

describe("where the claim invitation points", () => {
  it("sends a signed-out reader to the promoter sign-up", () => {
    expect(claimTarget(false, null)).toBe("/auth?kind=pro");
  });

  it("sends a signed-in reader to the account screen that grants the role", () => {
    expect(claimTarget(true, "user")).toBe("/account");
  });

  it("sends a promoter to their own surface", () => {
    expect(claimTarget(true, "pro")).toBe("/pro");
    expect(claimTarget(true, "admin")).toBe("/pro");
  });
});

describe("saving a card", () => {
  it("shows no save control at all when the page passes no handler", () => {
    // What a signed-out reader gets. A pill that cannot save is a promise
    // broken once per card.
    renderCard(BERGAMO);
    expect(screen.queryByRole("button", { name: /^save$/i })).not.toBeInTheDocument();
  });

  it("asks the page to save, and says which card and which direction", async () => {
    const user = userEvent.setup();
    const onToggleSave = vi.fn();
    render(
      <MemoryRouter>
        <LanguageProvider>
          <EventCardView
            card={BERGAMO}
            language="en"
            claimTo="/auth?kind=pro"
            onToggleSave={onToggleSave}
          />
        </LanguageProvider>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: /^save$/i }));
    expect(onToggleSave).toHaveBeenCalledWith("e1", true);
  });

  it("carries the saved state in the label, not only in the colour", async () => {
    const user = userEvent.setup();
    const onToggleSave = vi.fn();
    render(
      <MemoryRouter>
        <LanguageProvider>
          <EventCardView
            card={BERGAMO}
            language="en"
            claimTo="/auth?kind=pro"
            saved
            onToggleSave={onToggleSave}
          />
        </LanguageProvider>
      </MemoryRouter>,
    );

    const pill = screen.getByRole("button", { name: /^saved$/i, pressed: true });
    await user.click(pill);
    expect(onToggleSave).toHaveBeenCalledWith("e1", false);
  });
});
