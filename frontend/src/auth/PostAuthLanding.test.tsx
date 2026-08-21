import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { becomePromoter, PromoterRefreshError } from "./becomePromoter";
import { PostAuthLanding } from "./PostAuthLanding";
import {
  CALLBACK_PATH,
  rememberDestination,
  rememberPendingPromoter,
  rememberPromoterOrg,
} from "./postAuth";
import { translations } from "@/i18n/translations";
import { LanguageProvider } from "@/i18n/useTranslation";

const mocks = vi.hoisted(() => ({
  auth: {
    user: { id: "user-1", email: "promoter@example.com" } as { id: string; email?: string } | null,
    isLoading: false,
  },
}));

vi.mock("@/auth/AuthProvider", () => ({ useAuth: () => mocks.auth }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("./becomePromoter", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./becomePromoter")>();
  return { ...actual, becomePromoter: vi.fn() };
});

const grant = vi.mocked(becomePromoter);
const en = translations.en;

beforeEach(() => {
  mocks.auth = { user: { id: "user-1", email: "promoter@example.com" }, isLoading: false };
  grant.mockReset().mockResolvedValue(undefined);
  vi.mocked(toast.error).mockReset();
});

function renderLandingAt(path: string) {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[path]}>
        <PostAuthLanding />
        <Routes>
          <Route path={CALLBACK_PATH} element={<p>waiting room</p>} />
          <Route path="/" element={<p>chat</p>} />
          <Route path="/pro" element={<p>pro area</p>} />
          <Route path="/account" element={<p>account</p>} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  );
}

describe("coming back from OAuth", () => {
  it("holds the waiting room until the promoter row and the token have landed", async () => {
    let finishGrant!: () => void;
    grant.mockReturnValue(
      new Promise<void>((resolve) => {
        finishGrant = () => resolve();
      }),
    );
    rememberDestination("/pro");
    rememberPromoterOrg("Sala Apolo");

    renderLandingAt(CALLBACK_PATH);
    await act(async () => {
      await Promise.resolve();
    });

    // The whole point: /pro reads the role off the token, so reaching it
    // before the refresh means being refused and then watching it flip.
    expect(screen.getByText("waiting room")).toBeInTheDocument();
    expect(screen.queryByText("pro area")).not.toBeInTheDocument();

    await act(async () => {
      finishGrant();
      await Promise.resolve();
    });

    expect(await screen.findByText("pro area")).toBeInTheDocument();
    expect(grant).toHaveBeenCalledWith("user-1", "Sala Apolo");
  });

  it("forwards an ordinary sign-in without touching the promoter path", async () => {
    rememberDestination("/");

    renderLandingAt(CALLBACK_PATH);

    expect(await screen.findByText("chat")).toBeInTheDocument();
    expect(grant).not.toHaveBeenCalled();
  });

  it("never leaves anyone in the waiting room when the stash was lost", async () => {
    renderLandingAt(CALLBACK_PATH);

    expect(await screen.findByText("chat")).toBeInTheDocument();
  });

  it("finishes on /account when the grant fails, not on the refusal screen", async () => {
    rememberDestination("/pro");
    rememberPromoterOrg("Sala Apolo");
    grant.mockRejectedValue(new Error("row level security"));

    renderLandingAt(CALLBACK_PATH);

    expect(await screen.findByText("account")).toBeInTheDocument();
    expect(toast.error).toHaveBeenCalledWith(en.auth.promoterSetupFailed);
  });

  it("says something different when only the token is stale", async () => {
    rememberDestination("/pro");
    rememberPromoterOrg("Sala Apolo");
    grant.mockRejectedValue(new PromoterRefreshError("network"));

    renderLandingAt(CALLBACK_PATH);

    expect(await screen.findByText("account")).toBeInTheDocument();
    expect(toast.error).toHaveBeenCalledWith(en.auth.promoterSessionStale);
  });
});

describe("coming back from a confirmation mail", () => {
  it("spends the intent left for that address and opens /pro", async () => {
    // No round-trip stash at all: the mail was opened in another tab.
    rememberPendingPromoter("promoter@example.com", "Sala Apolo");

    renderLandingAt("/");

    expect(await screen.findByText("pro area")).toBeInTheDocument();
    expect(grant).toHaveBeenCalledWith("user-1", "Sala Apolo");
  });

  it("leaves someone else's intent alone", async () => {
    rememberPendingPromoter("other@example.com", "Sala Apolo");

    renderLandingAt("/");

    expect(await screen.findByText("chat")).toBeInTheDocument();
    expect(grant).not.toHaveBeenCalled();
  });
});

describe("before there is a session", () => {
  it("does nothing at all", async () => {
    mocks.auth = { user: null, isLoading: true };
    rememberDestination("/pro");
    rememberPromoterOrg("Sala Apolo");

    renderLandingAt(CALLBACK_PATH);
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText("waiting room")).toBeInTheDocument();
    expect(grant).not.toHaveBeenCalled();
  });
});
