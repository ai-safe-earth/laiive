import { afterEach, describe, expect, it, vi } from "vitest";
import {
  clearPostAuth,
  rememberDestination,
  rememberPendingPromoter,
  rememberPromoterOrg,
  takeDestination,
  takePendingPromoter,
  takePromoterOrg,
} from "./postAuth";

afterEach(() => {
  vi.useRealTimers();
});

describe("the round-trip stashes", () => {
  it("remembers '/' too, because the callback is never a destination", () => {
    rememberDestination("/");
    expect(takeDestination()).toBe("/");
  });

  it("spends a destination exactly once", () => {
    rememberDestination("/pro");
    expect(takeDestination()).toBe("/pro");
    expect(takeDestination()).toBeNull();
  });

  it("spends an organisation exactly once, trimmed", () => {
    rememberPromoterOrg("  Sala Apolo  ");
    expect(takePromoterOrg()).toBe("Sala Apolo");
    expect(takePromoterOrg()).toBeNull();
  });

  it("stashes nothing for a blank organisation", () => {
    rememberPromoterOrg("   ");
    expect(takePromoterOrg()).toBeNull();
  });
});

describe("the pending promoter", () => {
  it("waits for the address it was typed for", () => {
    rememberPendingPromoter("Promoter@Example.com", "Sala Apolo");
    expect(takePendingPromoter("someone.else@example.com")).toBeNull();
    // Left in place for its owner, not spent by the mismatch above.
    expect(takePendingPromoter("promoter@example.com")).toBe("Sala Apolo");
    expect(takePendingPromoter("promoter@example.com")).toBeNull();
  });

  it("is not cleared by an abandoned round trip", () => {
    // /auth clears the OAuth stashes on mount, and waiting for a confirmation
    // mail means sitting on /auth — the intent has to survive that.
    rememberDestination("/pro");
    rememberPromoterOrg("Sala Apolo");
    rememberPendingPromoter("promoter@example.com", "Sala Apolo");

    clearPostAuth();

    expect(takeDestination()).toBeNull();
    expect(takePromoterOrg()).toBeNull();
    expect(takePendingPromoter("promoter@example.com")).toBe("Sala Apolo");
  });

  it("expires rather than ambushing a much later sign-in", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-21T10:00:00Z"));
    rememberPendingPromoter("promoter@example.com", "Sala Apolo");

    vi.setSystemTime(new Date("2026-08-22T10:00:01Z"));
    expect(takePendingPromoter("promoter@example.com")).toBeNull();
  });

  it("survives its own TTL until it runs out", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-21T10:00:00Z"));
    rememberPendingPromoter("promoter@example.com", "Sala Apolo");

    vi.setSystemTime(new Date("2026-08-21T22:00:00Z"));
    expect(takePendingPromoter("promoter@example.com")).toBe("Sala Apolo");
  });

  it("drops an unreadable stash instead of throwing on every sign-in", () => {
    localStorage.setItem("laiive-pending-promoter", "{not json");
    expect(takePendingPromoter("promoter@example.com")).toBeNull();
    expect(localStorage.getItem("laiive-pending-promoter")).toBeNull();
  });

  it("stashes nothing without both an address and an organisation", () => {
    rememberPendingPromoter("", "Sala Apolo");
    rememberPendingPromoter("promoter@example.com", "  ");
    expect(takePendingPromoter("promoter@example.com")).toBeNull();
  });
});
