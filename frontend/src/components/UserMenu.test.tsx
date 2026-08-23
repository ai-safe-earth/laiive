import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { UserMenu } from "./UserMenu";
import { LanguageProvider } from "@/i18n/useTranslation";
import { translations } from "@/i18n/translations";

const auth = vi.hoisted(() => ({
  state: {
    user: { id: "user-1", email: "promoter@example.com" } as unknown,
    role: "pro",
    signOut: () => Promise.resolve(),
  },
}));

vi.mock("@/auth/AuthProvider", () => ({ useAuth: () => auth.state }));

beforeEach(() => {
  auth.state.role = "pro";
});

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

describe("who sees a door to the other surface", () => {
  /** Opens the menu and returns every link label inside it. */
  async function openMenuAt(path: string) {
    const user = userEvent.setup();
    renderMenuAt(path);
    await user.click(screen.getByRole("button", { name: en.menu.aria }));
    return screen.getAllByRole("link").map((link) => link.textContent);
  }

  it("offers a promoter the promoter surface from the chat", async () => {
    const labels = await openMenuAt("/");
    expect(labels).toContain(en.menu.pro);
    expect(labels).not.toContain(en.menu.toLaiive);
  });

  it("offers the way back once the promoter is on /pro", async () => {
    const labels = await openMenuAt("/pro");
    expect(labels).toContain(en.menu.toLaiive);
    // Both at once would be one of them pointing at the page you are on.
    expect(labels).not.toContain(en.menu.pro);
  });

  it("shows a plain user neither door, nor the admin one", async () => {
    auth.state.role = "user";
    const labels = await openMenuAt("/");
    expect(labels).not.toContain(en.menu.pro);
    expect(labels).not.toContain(en.menu.toLaiive);
    expect(labels).not.toContain("Admin");
  });

  it("shows an admin the review queue as well", async () => {
    auth.state.role = "admin";
    const labels = await openMenuAt("/");
    expect(labels).toContain("Admin");
    expect(labels).toContain(en.menu.pro);
  });
});
