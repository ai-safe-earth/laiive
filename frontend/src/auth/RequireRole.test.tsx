import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { RequireRole } from "./RequireRole";

const auth = vi.hoisted(() => ({
  state: { user: null as unknown, role: "user", isLoading: false },
}));

vi.mock("@/auth/AuthProvider", () => ({ useAuth: () => auth.state }));

function renderGuard(minimum: "pro" | "admin" = "admin") {
  return render(
    <MemoryRouter initialEntries={["/admin"]}>
      <Routes>
        <Route
          path="/admin"
          element={
            <RequireRole minimum={minimum}>
              <p>the admin screen</p>
            </RequireRole>
          }
        />
        <Route path="/" element={<p>the chat</p>} />
        <Route path="/auth" element={<p>the sign-in form</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("the role gate", () => {
  it("shows nothing while the session is still loading", () => {
    auth.state = { user: null, role: "user", isLoading: true };
    const { container } = renderGuard();
    // Deciding before the token is read shows a refusal to someone who is
    // signed in, and then flips under them.
    expect(container.textContent).toBe("");
  });

  it("sends an anonymous visitor to sign in", () => {
    auth.state = { user: null, role: "user", isLoading: false };
    renderGuard();
    expect(screen.getByText("the sign-in form")).toBeTruthy();
  });

  it("does not send a signed-in user to a form they are already past", () => {
    // The dead end this exists to avoid: /auth would just bounce them back.
    auth.state = { user: { id: "u1" }, role: "user", isLoading: false };
    renderGuard();
    expect(screen.queryByText("the sign-in form")).toBeNull();
    expect(screen.getByText("the chat")).toBeTruthy();
  });

  it("lets an admin through", () => {
    auth.state = { user: { id: "u1" }, role: "admin", isLoading: false };
    renderGuard();
    expect(screen.getByText("the admin screen")).toBeTruthy();
  });

  it("treats admin as satisfying a pro gate", () => {
    auth.state = { user: { id: "u1" }, role: "admin", isLoading: false };
    renderGuard("pro");
    expect(screen.getByText("the admin screen")).toBeTruthy();
  });

  it("refuses a pro at an admin gate", () => {
    auth.state = { user: { id: "u1" }, role: "pro", isLoading: false };
    renderGuard();
    expect(screen.queryByText("the admin screen")).toBeNull();
  });
});
