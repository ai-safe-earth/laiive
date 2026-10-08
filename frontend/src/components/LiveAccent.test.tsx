import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Button } from "@/components/ui/Button";
import { LiveAccent } from "./LiveAccent";

/**
 * The world only lines up if every hole carries `.live-accent` (the hook finds
 * them by it) and a mask names its stencil. Pinned because a missing class
 * fails silently: the accent just goes flat.
 */
describe("live accents", () => {
  it("cuts a mask from the named stencil", () => {
    const { container } = render(<LiveAccent variant="mask" mask="saved" />);
    expect(container.firstElementChild?.className).toMatch(
      /live-accent .*live-accent--mask.*live-saved/,
    );
  });

  it("is live on the primary button only", () => {
    const { getAllByRole } = render(
      <>
        <Button>go</Button>
        <Button variant="cyan">pro</Button>
      </>,
    );
    const [primary, cyan] = getAllByRole("button");
    expect(primary?.className).toContain("live-accent");
    expect(cyan?.className).not.toContain("live-accent");
  });
});
