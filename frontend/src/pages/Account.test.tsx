import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Account from "./Account";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

const en = translations.en;

const auth = vi.hoisted(() => ({
  state: { user: { id: "u1", email: "p@example.com" }, role: "pro", isLoading: false },
}));
vi.mock("@/auth/AuthProvider", () => ({ useAuth: () => auth.state }));

const data = vi.hoisted(() => ({ orgs: [] as unknown[] }));
vi.mock("@/api/organizations", () => ({
  useMyOrgs: () => ({ data: data.orgs }),
  useOrgClaims: () => ({ data: [] }),
}));
vi.mock("@/api/profile", () => ({
  useProfile: () => ({ data: { id: "u1", display_name: "Oscar" }, isLoading: false }),
  useUpdateProfile: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

function renderFrom(from?: string) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: "/account", state: from ? { from } : null }]}>
      <LanguageProvider>
        <Account />
      </LanguageProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  auth.state = { user: { id: "u1", email: "p@example.com" }, role: "pro", isLoading: false };
  data.orgs = [];
});

describe("/account and the promoter", () => {
  it("points at /pro/org instead of asking for the organisation again", () => {
    data.orgs = [{ id: "org-1", display_name: "Razzmatazz", role: "owner" }];
    renderFrom("/pro");
    expect(screen.getByText("Razzmatazz")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: en.org.manage })).toHaveAttribute("href", "/pro/org");
    // The old free-text form asked identity a third time; it is gone.
    expect(screen.queryByPlaceholderText(en.auth.orgPlaceholder)).not.toBeInTheDocument();
  });

  it("sends a plain user to /pro, where the question is asked once", () => {
    auth.state.role = "user";
    renderFrom();
    expect(screen.getByRole("link", { name: en.account.becomePromoterCta })).toHaveAttribute(
      "href",
      "/pro",
    );
  });

  it("wears the promoter ground when opened from /pro, and not from the chat", () => {
    const { container, unmount } = renderFrom("/pro");
    expect(container.firstElementChild?.className).toContain("bg-pro-bg");
    unmount();
    const consumer = renderFrom();
    expect(consumer.container.firstElementChild?.className).toContain("bg-background");
  });
});
