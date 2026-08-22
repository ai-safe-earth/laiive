import type { EventCard } from "@shared/protocol";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { EventCardView } from "./EventCardView";
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

function renderCard(card: EventCard) {
  return render(
    <LanguageProvider>
      <EventCardView card={card} language="en" />
    </LanguageProvider>,
  );
}

describe("the time a card prints", () => {
  it("shows the hour at the venue, not on the reader's clock", () => {
    // jsdom runs on this machine's zone; the card must ignore it. Read in UTC
    // this is 20:00 on the 22nd, and in New York 16:00 — neither is the answer.
    renderCard(BERGAMO);
    // "en" formats 12-hour: 22:00 in Rome reads as 10:00 PM on the 22nd.
    expect(screen.getByText(/Aug 22, 10:00 PM|Aug 22, 10:00 PM/)).toBeTruthy();
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
    expect(screen.getByText(/Aug 22, 11:30 PM|Aug 22, 11:30 PM/)).toBeTruthy();
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

  it("invites the promoter to take the listing over", async () => {
    const user = userEvent.setup();
    renderCard(WEB);
    await user.click(screen.getByRole("button", { name: /where did this come from/i }));
    expect(screen.getByText(/promoter account/i)).toBeTruthy();
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
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText(/promoter account/i)).toBeTruthy();
  });

  it("gives a seed row neither mark", () => {
    renderCard({ ...BERGAMO, source: "seed" });
    expect(screen.queryByRole("button", { name: /where did this come from/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /who confirmed this/i })).toBeNull();
  });
});
