import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Auth from "./Auth";
import { becomePromoter, PromoterRefreshError } from "@/auth/becomePromoter";
import { takeDestination, takePendingPromoter, takePromoterOrg } from "@/auth/postAuth";
import { translations } from "@/i18n/translations";
import { LanguageProvider } from "@/i18n/useTranslation";

const mocks = vi.hoisted(() => ({
  signIn: vi.fn(),
  signUp: vi.fn(),
  signInWithGoogle: vi.fn(),
}));

vi.mock("@/auth/AuthProvider", () => ({ useAuth: () => mocks }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("@/auth/becomePromoter", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/auth/becomePromoter")>();
  return { ...actual, becomePromoter: vi.fn() };
});

const grant = vi.mocked(becomePromoter);
const en = translations.en;

beforeEach(() => {
  mocks.signIn.mockReset().mockResolvedValue(undefined);
  mocks.signUp.mockReset().mockResolvedValue({ signedIn: true, userId: "user-1" });
  mocks.signInWithGoogle.mockReset().mockResolvedValue(undefined);
  grant.mockReset().mockResolvedValue(undefined);
  vi.mocked(toast.error).mockReset();
  vi.mocked(toast.success).mockReset();
});

function renderAuthAt(path: string) {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/auth" element={<Auth />} />
          <Route path="/" element={<p>chat</p>} />
          <Route path="/pro" element={<p>pro area</p>} />
          <Route path="/account" element={<p>account</p>} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  );
}

/** Everything the pro door asks for, in the order it asks. */
async function fillProSignUp(user: ReturnType<typeof userEvent.setup>, org: string) {
  if (org) await user.type(screen.getByPlaceholderText(en.auth.orgPlaceholder), org);
  await user.type(screen.getByPlaceholderText(en.auth.emailPlaceholder), "promoter@example.com");
  await user.type(screen.getByPlaceholderText(en.auth.passwordPlaceholder), "hunter2hunter2");
}

describe("the promoter door, by email", () => {
  it("refuses a whitespace organisation before creating anything", async () => {
    const user = userEvent.setup();
    renderAuthAt("/auth?kind=pro");

    await fillProSignUp(user, "   ");
    await user.click(screen.getByRole("button", { name: en.auth.signUp }));

    // `required` is happy with a space; becomePromoter is not — and the
    // account would already exist by the time it said so.
    expect(mocks.signUp).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(en.auth.orgRequired);
    expect(screen.queryByText("pro area")).not.toBeInTheDocument();
  });

  it("writes the account and the promoter row, then opens /pro", async () => {
    const user = userEvent.setup();
    renderAuthAt("/auth?kind=pro");

    await fillProSignUp(user, "Sala Apolo");
    await user.click(screen.getByRole("button", { name: en.auth.signUp }));

    expect(grant).toHaveBeenCalledWith("user-1", "Sala Apolo");
    expect(await screen.findByText("pro area")).toBeInTheDocument();
  });

  it("keeps the organisation waiting when a confirmation mail comes first", async () => {
    mocks.signUp.mockResolvedValue({ signedIn: false, userId: null });
    const user = userEvent.setup();
    renderAuthAt("/auth?kind=pro");

    await fillProSignUp(user, "Sala Apolo");
    await user.click(screen.getByRole("button", { name: en.auth.signUp }));

    expect(toast.success).toHaveBeenCalledWith(en.auth.checkInbox);
    // The mail is opened elsewhere, so the intent has to outlive this tab —
    // otherwise the door quietly produces an ordinary account.
    expect(takePendingPromoter("promoter@example.com")).toBe("Sala Apolo");
  });

  it("finishes on /account when only the token is stale", async () => {
    grant.mockRejectedValue(new PromoterRefreshError("network"));
    const user = userEvent.setup();
    renderAuthAt("/auth?kind=pro");

    await fillProSignUp(user, "Sala Apolo");
    await user.click(screen.getByRole("button", { name: en.auth.signUp }));

    expect(await screen.findByText("account")).toBeInTheDocument();
    expect(toast.error).toHaveBeenCalledWith(en.auth.promoterSessionStale);
  });

  it("finishes on /account when the promoter row never landed", async () => {
    grant.mockRejectedValue(new Error("row level security"));
    const user = userEvent.setup();
    renderAuthAt("/auth?kind=pro");

    await fillProSignUp(user, "Sala Apolo");
    await user.click(screen.getByRole("button", { name: en.auth.signUp }));

    expect(await screen.findByText("account")).toBeInTheDocument();
    expect(toast.error).toHaveBeenCalledWith(en.auth.promoterSetupFailed);
  });
});

describe("the promoter door, by google", () => {
  it("leaves through the waiting room, not straight at /pro", async () => {
    const user = userEvent.setup();
    renderAuthAt("/auth?kind=pro");

    await user.type(screen.getByPlaceholderText(en.auth.orgPlaceholder), "Sala Apolo");
    await user.click(screen.getByRole("button", { name: en.auth.google }));

    expect(mocks.signInWithGoogle).toHaveBeenCalledWith(
      `${window.location.origin}/auth/callback`,
    );
    expect(takeDestination()).toBe("/pro");
    expect(takePromoterOrg()).toBe("Sala Apolo");
  });

  it("does not leave at all without an organisation", async () => {
    const user = userEvent.setup();
    renderAuthAt("/auth?kind=pro");

    await user.click(screen.getByRole("button", { name: en.auth.google }));

    expect(mocks.signInWithGoogle).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(en.auth.orgRequired);
  });
});

describe("the ordinary door", () => {
  it("still stashes where it is going, because the callback needs a next step", async () => {
    const user = userEvent.setup();
    renderAuthAt("/auth");

    await user.click(screen.getByRole("button", { name: en.auth.google }));

    expect(mocks.signInWithGoogle).toHaveBeenCalledWith(
      `${window.location.origin}/auth/callback`,
    );
    expect(takeDestination()).toBe("/");
    expect(takePromoterOrg()).toBeNull();
  });
});
