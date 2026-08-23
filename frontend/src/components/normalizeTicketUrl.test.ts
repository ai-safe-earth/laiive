import { describe, expect, it } from "vitest";
import { INVALID_URL, normalizeTicketUrl } from "./EventForm";

describe("the ticket link a promoter types", () => {
  it("is left alone when it already carries a scheme", () => {
    expect(normalizeTicketUrl("https://dice.fm/event/xyz")).toBe("https://dice.fm/event/xyz");
  });

  it("gets https when it was typed the way it is spoken", () => {
    // Stored bare it becomes a relative href, and the card's tickets pill
    // would send a reader to laiive.com/dice.fm/…
    expect(normalizeTicketUrl("dice.fm/event/xyz")).toBe("https://dice.fm/event/xyz");
  });

  it("keeps http rather than silently upgrading somebody's own box", () => {
    expect(normalizeTicketUrl("http://druso.it/live")).toBe("http://druso.it/live");
  });

  it("trims, because a pasted link brings its whitespace", () => {
    expect(normalizeTicketUrl("  dice.fm  ")).toBe("https://dice.fm/");
  });

  it("reads an empty field as no link, not as a bad one", () => {
    expect(normalizeTicketUrl("")).toBeNull();
    expect(normalizeTicketUrl("   ")).toBeNull();
    expect(normalizeTicketUrl(null)).toBeNull();
    expect(normalizeTicketUrl(undefined)).toBeNull();
  });

  it("refuses something that is not a web address", () => {
    expect(normalizeTicketUrl("ask at the door")).toBe(INVALID_URL);
    expect(normalizeTicketUrl("localhost:3000")).toBe(INVALID_URL);
    expect(normalizeTicketUrl("javascript:alert(1)")).toBe(INVALID_URL);
    expect(normalizeTicketUrl("mailto:box@druso.it")).toBe(INVALID_URL);
  });
});
