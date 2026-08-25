import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AdminStats } from "./AdminStats";
import { A } from "./strings";

// The error branch, with the hook mocked whole: driving a real rejected fetch
// through react-query v5 trips vitest's unhandled-rejection detector before
// the library's own handlers attach, so the failing-network case is pinned
// here at the hook boundary instead. Its own file because vi.mock is
// file-scoped and every other AdminStats spec needs the real hook.
vi.mock("@/api/admin", () => ({
  useStats: () => ({ isLoading: false, isError: true, data: undefined }),
}));

describe("the numbers above the queue, when they cannot load", () => {
  it("keeps the queue usable and says the numbers failed", () => {
    render(<AdminStats />);
    expect(screen.getByText(A.stats.failed)).toBeInTheDocument();
  });
});
