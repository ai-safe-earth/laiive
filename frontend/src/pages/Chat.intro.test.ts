import { afterEach, describe, expect, it, vi } from "vitest";
import { introAt } from "./Chat";

/**
 * Three ways the opening film stands down. Worth pinning because two of them
 * are invisible in normal use: nobody notices a film that correctly does not
 * play, and the promoter case only shows up crossing back from /pro.
 */
function motion(reduced: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: reduced })) as unknown as typeof window.matchMedia,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("whether the opening film plays", () => {
  it("plays for somebody arriving at laiive", () => {
    motion(false);
    expect(introAt(null)).toBe("playing");
    expect(introAt({ from: "/saved" })).toBe("playing");
  });

  it("stands down for a promoter crossing back from their own surface", () => {
    motion(false);
    expect(introAt({ from: "/pro" })).toBe("done");
    expect(introAt({ from: "/pro/org" })).toBe("done");
    expect(introAt({ from: "/admin" })).toBe("done");
  });

  it("stands down when the reader has asked for less motion", () => {
    motion(true);
    expect(introAt(null)).toBe("done");
  });

  it("stands down rather than guess when the browser cannot say", () => {
    // An unskippable film over the one thing on the screen is worse than none.
    vi.stubGlobal("matchMedia", () => {
      throw new Error("no matchMedia");
    });
    expect(introAt(null)).toBe("done");
  });
});
