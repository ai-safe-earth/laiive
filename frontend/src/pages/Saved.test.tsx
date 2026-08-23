import type { EventCard } from "@shared/protocol";
import { describe, expect, it } from "vitest";
import { splitByTime } from "./Saved";

const NOW = new Date("2026-08-23T12:00:00Z").getTime();

function card(uid: string, startAt: string | null): EventCard {
  return { uid, name: uid, artists: [], start_at: startAt, source: "pro_submission" };
}

describe("how a saved list is ordered", () => {
  it("puts what is still coming first, soonest first", () => {
    const { upcoming } = splitByTime(
      [
        card("later", "2026-09-01T20:00:00Z"),
        card("soon", "2026-08-24T20:00:00Z"),
      ],
      NOW,
    );
    expect(upcoming.map((c) => c.uid)).toEqual(["soon", "later"]);
  });

  it("keeps what has happened, most recent first", () => {
    // Saving something does not stop being a fact once the night is over, and
    // a card silently vanishing on the day would look like data loss.
    const { upcoming, past } = splitByTime(
      [
        card("old", "2026-01-04T20:00:00Z"),
        card("recent", "2026-08-20T20:00:00Z"),
      ],
      NOW,
    );
    expect(upcoming).toEqual([]);
    expect(past.map((c) => c.uid)).toEqual(["recent", "old"]);
  });

  it("treats a card with no usable date as still to come", () => {
    // It has not been shown to be over, and burying it under "already
    // happened" claims something the row does not say.
    const { upcoming } = splitByTime([card("undated", null), card("junk", "whenever")], NOW);
    expect(upcoming.map((c) => c.uid)).toEqual(["undated", "junk"]);
  });
});
