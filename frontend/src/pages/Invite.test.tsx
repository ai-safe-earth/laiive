import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Invite from "./Invite";
import { ApiError } from "@/api/client";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

const en = translations.en;

const auth = vi.hoisted(() => ({
  state: { user: { id: "u1" } as { id: string } | null, role: "user", isLoading: false },
}));
vi.mock("@/auth/AuthProvider", () => ({ useAuth: () => auth.state }));

const nav = vi.hoisted(() => ({ go: vi.fn() }));
vi.mock("react-router-dom", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router-dom")>()),
  useNavigate: () => nav.go,
}));

const api = vi.hoisted(() => ({ accept: vi.fn(), refresh: vi.fn() }));
vi.mock("@/api/organizations", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/organizations")>()),
  acceptInvitation: api.accept,
}));
vi.mock("@/auth/becomePromoter", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/auth/becomePromoter")>()),
  refreshRole: api.refresh,
}));

const stash = vi.hoisted(() => ({ remember: vi.fn() }));
vi.mock("@/auth/postAuth", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/auth/postAuth")>()),
  rememberDestination: stash.remember,
}));

const toasts = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast: toasts }));

function renderAt(token = "tok-123") {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <LanguageProvider>
        <MemoryRouter initialEntries={[`/invite/${token}`]}>
          <Routes>
            <Route path="/invite/:token" element={<Invite />} />
          </Routes>
        </MemoryRouter>
      </LanguageProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  auth.state = { user: { id: "u1" }, role: "user", isLoading: false };
  nav.go.mockReset();
  api.accept.mockReset().mockResolvedValue({ org_id: "org-1", role: "member", already: false });
  api.refresh.mockReset().mockResolvedValue(undefined);
  stash.remember.mockReset();
  toasts.success.mockReset();
  toasts.error.mockReset();
});

describe("/invite/:token", () => {
  it("sends a signed-out visitor through the front door, remembering the link", () => {
    // The person an invitation is for usually has no account at all. The stash
    // is how the intent survives a sign-in that leaves the app (Google) or
    // stands behind a confirmation mail.
    auth.state = { user: null, role: "user", isLoading: false };
    renderAt();

    expect(stash.remember).toHaveBeenCalledWith("/invite/tok-123");
    expect(nav.go).toHaveBeenCalledWith("/auth", { replace: true });
    expect(api.accept).not.toHaveBeenCalled();
  });

  it("redeems the token, re-mints the session, and lands on the organisation", async () => {
    renderAt();

    await waitFor(() => expect(api.accept).toHaveBeenCalledWith("tok-123"));
    // The role rides in the JWT and is stamped at issue, so without this a
    // guest who has just become a promoter is refused by /pro for an hour.
    await waitFor(() => expect(api.refresh).toHaveBeenCalled());
    await waitFor(() => expect(nav.go).toHaveBeenCalledWith("/pro/org", { replace: true }));
    expect(toasts.success).toHaveBeenCalledWith(en.invite.welcome);
  });

  it("spends the token once, even though effects run twice in development", async () => {
    renderAt();
    await waitFor(() => expect(api.accept).toHaveBeenCalled());
    expect(api.accept).toHaveBeenCalledTimes(1);
  });

  it("says so plainly when the seat was already there", async () => {
    api.accept.mockResolvedValue({ org_id: "org-1", role: "member", already: true });
    renderAt();
    await waitFor(() => expect(toasts.success).toHaveBeenCalledWith(en.invite.alreadyIn));
  });

  it("lands on /account when the seat is real but the token would not re-mint", async () => {
    const { PromoterRefreshError } = await import("@/auth/becomePromoter");
    api.refresh.mockRejectedValue(new PromoterRefreshError("network"));
    renderAt();

    // They are in the organisation and the database says so — /pro would only
    // show a refusal against a stale claim.
    await waitFor(() => expect(nav.go).toHaveBeenCalledWith("/account", { replace: true }));
    expect(toasts.error).toHaveBeenCalledWith(en.invite.staleSession);
  });

  const dead: [number, string][] = [
    [404, en.invite.unknown],
    [409, en.invite.spent],
    [410, en.invite.expired],
  ];
  it.each(dead)("explains a %i rather than looping", async (status, message) => {
    api.accept.mockRejectedValue(new ApiError(status, "upstream wording"));
    renderAt();

    await waitFor(() => expect(screen.getByText(message)).toBeInTheDocument());
    expect(nav.go).not.toHaveBeenCalled();
  });

  it("passes the gateway's own words through on a wrong address", async () => {
    // The 403 names the invited address, which is the one useful thing to say:
    // it tells the holder which account to sign in as.
    api.accept.mockRejectedValue(
      new ApiError(403, "that invitation was sent to ana@sala.cat"),
    );
    renderAt();

    await waitFor(() =>
      expect(screen.getByText("that invitation was sent to ana@sala.cat")).toBeInTheDocument(),
    );
  });
});
