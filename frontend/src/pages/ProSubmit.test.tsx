import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProSubmit from "./ProSubmit";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

const en = translations.en;

const auth = vi.hoisted(() => ({
  state: {
    user: { id: "u1", email: "p@example.com" } as { id: string; email: string } | null,
    role: "pro",
    isLoading: false,
    signOut: () => Promise.resolve(),
  },
}));
vi.mock("@/auth/AuthProvider", () => ({ useAuth: () => auth.state }));

const data = vi.hoisted(() => ({ orgs: [] as unknown[] }));
vi.mock("@/api/organizations", () => ({
  useMyOrgs: () => ({ data: data.orgs, isLoading: false }),
  useCreateOrg: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock("@/api/profile", () => ({ usePromoterProfile: () => ({ data: null }) }));
vi.mock("@/auth/becomePromoter", () => ({ becomePromoter: vi.fn() }));
// jsdom has no layout; the chat scrolls to its last message on mount.
Element.prototype.scrollIntoView = vi.fn();

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/pro"]}>
      <LanguageProvider>
        <ProSubmit />
      </LanguageProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  auth.state = {
    user: { id: "u1", email: "p@example.com" },
    role: "pro",
    isLoading: false,
    signOut: () => Promise.resolve(),
  };
  data.orgs = [];
});

describe("who /pro asks to identify themselves", () => {
  it("asks a promoter who belongs to nothing yet", () => {
    renderPage();
    expect(screen.getByText(en.org.noneTitle)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(en.pro.placeholder)).not.toBeInTheDocument();
  });

  it("asks a plain user the same question — it is the door", () => {
    auth.state.role = "user";
    renderPage();
    expect(screen.getByText(en.org.noneTitle)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: en.pro.signInLink })).not.toBeInTheDocument();
  });

  it("lets a promoter with an organisation straight in, named", () => {
    data.orgs = [{ id: "org-1", kind: "venue", display_name: "Razzmatazz", role: "owner" }];
    renderPage();
    expect(screen.queryByText(en.org.noneTitle)).not.toBeInTheDocument();
    expect(screen.getByText("Razzmatazz")).toBeInTheDocument();
  });

  it("never asks an admin", () => {
    auth.state.role = "admin";
    renderPage();
    expect(screen.queryByText(en.org.noneTitle)).not.toBeInTheDocument();
  });

  it("sends a visitor to sign up, not to the form", () => {
    auth.state.user = null;
    renderPage();
    expect(screen.queryByText(en.org.noneTitle)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: en.pro.signInLink })).toHaveAttribute(
      "href",
      "/auth?kind=pro",
    );
  });
});
