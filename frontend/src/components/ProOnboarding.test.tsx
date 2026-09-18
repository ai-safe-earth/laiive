import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ProOnboarding } from "./ProOnboarding";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

const en = translations.en;

function renderPanel() {
  return render(
    <LanguageProvider>
      <ProOnboarding />
    </LanguageProvider>,
  );
}

describe("the promoter walkthrough", () => {
  it("shows on a first visit", () => {
    // setup.ts clears storage between tests, so this is a fresh promoter.
    renderPanel();
    expect(
      screen.getByRole("checkbox", { name: en.pro.onboardingDismiss }),
    ).toBeInTheDocument();
  });

  it("paints its own panel ground", () => {
    // bg-pro-bg-card was never a generated class; the panel sat transparent.
    renderPanel();
    const section = screen
      .getByRole("checkbox", { name: en.pro.onboardingDismiss })
      .closest("section");
    expect(section?.className).toContain("bg-pro-card");
  });

  it("plays the walkthrough at three-quarter speed", () => {
    // Both rates: the media load algorithm resets playbackRate to
    // defaultPlaybackRate, so pinning only playbackRate snaps back to 1x.
    const { container } = renderPanel();
    const video = container.querySelector("video");
    expect(video?.playbackRate).toBe(0.75);
    expect(video?.defaultPlaybackRate).toBe(0.75);
  });

  it("names the video, now that the steps beside it are gone", () => {
    // It used to be aria-hidden with the numbered steps carrying the account
    // of the same four moves. The steps went; the name has to stay.
    renderPanel();
    expect(screen.getByLabelText(en.pro.onboardingVideo).tagName).toBe("VIDEO");
  });

  it("stays gone once the box is ticked", async () => {
    const user = userEvent.setup();
    const { unmount } = renderPanel();

    await user.click(screen.getByRole("checkbox", { name: en.pro.onboardingDismiss }));
    expect(
      screen.queryByRole("checkbox", { name: en.pro.onboardingDismiss }),
    ).not.toBeInTheDocument();

    // The point of the flag: a reload must not bring it back.
    unmount();
    renderPanel();
    expect(
      screen.queryByRole("checkbox", { name: en.pro.onboardingDismiss }),
    ).not.toBeInTheDocument();
  });

  it("shows anyway when storage refuses to answer", async () => {
    // Private mode throws on getItem. Showing a panel one extra time is a far
    // better failure than a blank /pro.
    const original = Storage.prototype.getItem;
    // Only our key: the language provider reads storage unguarded on the
    // way in, and breaking that would be testing a different bug.
    Storage.prototype.getItem = function (key: string) {
      if (key === "laiive-pro-onboarding-seen") throw new Error("denied");
      return original.call(this, key);
    };
    try {
      renderPanel();
      expect(
        screen.getByRole("checkbox", { name: en.pro.onboardingDismiss }),
      ).toBeInTheDocument();
    } finally {
      Storage.prototype.getItem = original;
    }
  });
});
