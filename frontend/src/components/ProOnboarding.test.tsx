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
    expect(screen.getByText(en.pro.onboardingTitle)).toBeInTheDocument();
  });

  it("stays gone after it is dismissed", async () => {
    const user = userEvent.setup();
    const { unmount } = renderPanel();

    await user.click(screen.getByRole("button", { name: en.pro.onboardingDismiss }));
    expect(screen.queryByText(en.pro.onboardingTitle)).not.toBeInTheDocument();

    // The point of the flag: a reload must not bring it back.
    unmount();
    renderPanel();
    expect(screen.queryByText(en.pro.onboardingTitle)).not.toBeInTheDocument();
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
      expect(screen.getByText(en.pro.onboardingTitle)).toBeInTheDocument();
    } finally {
      Storage.prototype.getItem = original;
    }
  });
});
