import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { UserMenu } from "./UserMenu";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

vi.mock("@/auth/AuthProvider", () => ({
  useAuth: () => ({
    user: { id: "user-1", email: "promoter@example.com" },
    role: "pro",
    signOut: vi.fn(),
  }),
}));

/** Stands in for /account, which reads exactly this to point its back arrow. */
function AccountStub() {
  const location = useLocation() as { state?: { from?: string } };
  return <p>came from: {location.state?.from ?? "(nothing)"}</p>;
}

function renderMenuAt(path: string) {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={path} element={<UserMenu />} />
          <Route path="/account" element={<AccountStub />} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  );
}

const en = translations.en;

describe("the account menu", () => {
  it("tells /account it was opened from /pro", async () => {
    const user = userEvent.setup();
    renderMenuAt("/pro");

    await user.click(screen.getByRole("button", { name: en.menu.aria }));
    await user.click(screen.getByRole("link", { name: en.menu.settings }));

    // Without this the promoter's back arrow lands on the consumer chat,
    // which is a different product wearing the same header.
    expect(screen.getByText(/came from: \/pro/)).toBeInTheDocument();
  });

  it("tells it the chat when that is where it was opened", async () => {
    const user = userEvent.setup();
    renderMenuAt("/");

    await user.click(screen.getByRole("button", { name: en.menu.aria }));
    await user.click(screen.getByRole("link", { name: en.menu.settings }));

    expect(screen.getByText(/came from: \//)).toBeInTheDocument();
  });
});
