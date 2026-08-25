import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminReport from "./AdminReport";

const api = vi.hoisted(() => ({ fetch: vi.fn() }));
vi.mock("@/api/client", () => ({
  apiFetch: api.fetch,
  ApiError: class extends Error {},
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const REPORT = {
  id: "r1",
  city: "Bergamo",
  status: "dry_run",
  kind: "sweep",
  error: null,
  stats: { new: 3, tavily_credits: 6 },
  created_at: "2026-08-23T09:12:59Z",
  approved_at: null,
  reviewed_at: null,
  write_results: null,
  candidates: [
    {
      draft: { name: "BobSin", venue: "Druso", start_at: "2026-09-04T21:00:00+02:00" },
      source_url: "https://www.drusobg.it/",
      missing: [],
      dedup_status: "new",
    },
    {
      draft: { name: "Already Known", venue: "Daste", start_at: "2026-09-05T21:00:00+02:00" },
      source_url: "https://www.dastebergamo.com/eventi/",
      missing: [],
      dedup_status: "exists",
    },
    {
      draft: { name: "Venueless Fest", start_at: "2026-09-06T21:00:00+02:00" },
      source_url: "https://eventbrite.it/x",
      missing: ["venue"],
      dedup_status: "new",
    },
  ],
};

function renderReport() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/admin/reports/r1"]}>
        <Routes>
          <Route path="/admin/reports/:id" element={<AdminReport />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  api.fetch.mockReset();
  api.fetch.mockResolvedValue({ json: async () => REPORT });
});

describe("the report screen", () => {
  it("shows every candidate with the page it came from", async () => {
    renderReport();
    expect(await screen.findByText("BobSin")).toBeTruthy();
    const link = screen.getByRole("link", { name: "drusobg.it" });
    expect(link.getAttribute("href")).toBe("https://www.drusobg.it/");
  });

  it("warns that a candidate with no venue will be refused", async () => {
    // The writer rejects it as invalid; saying so up front beats an "invalid"
    // row in the results afterwards.
    renderReport();
    expect(await screen.findByText(/will be refused/i)).toBeTruthy();
  });

  it("select-all takes the new ones and skips what cannot be written", async () => {
    const user = userEvent.setup();
    renderReport();
    await screen.findByText("BobSin");
    await user.click(screen.getByRole("button", { name: /select all new/i }));
    // Only BobSin: "Already Known" is a duplicate, "Venueless Fest" has no venue.
    expect(screen.getByText("1 selected")).toBeTruthy();
  });

  it("cannot approve with nothing selected", async () => {
    renderReport();
    await screen.findByText("BobSin");
    const approve = screen.getByRole("button", { name: /approve selected/i });
    expect(approve.hasAttribute("disabled")).toBe(true);
  });

  it("sends the chosen indices, not every candidate", async () => {
    const user = userEvent.setup();
    renderReport();
    await screen.findByText("BobSin");
    await user.click(screen.getByRole("checkbox", { name: "BobSin" }));
    api.fetch.mockResolvedValueOnce({
      json: async () => ({ report_id: "r1", created: 1, results: [], warnings: [] }),
    });
    await user.click(screen.getByRole("button", { name: /approve selected/i }));
    await waitFor(() => {
      const call = api.fetch.mock.calls.find(([path]) => String(path).includes("/approve"));
      expect(call).toBeTruthy();
      expect(JSON.parse(call![1].body)).toEqual({ indices: [0] });
    });
  });

  it("hides the actions once the report is settled", async () => {
    // A second approve would 409 anyway; offering the button invites it.
    api.fetch.mockResolvedValue({
      json: async () => ({ ...REPORT, status: "approved" }),
    });
    renderReport();
    await screen.findByText("BobSin");
    expect(screen.queryByRole("button", { name: /approve selected/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /dismiss report/i })).toBeNull();
  });
});

describe("dismissing a report", () => {
  it("does nothing when the note prompt is cancelled", async () => {
    // Cancel returns null. Dismissing is one-way (dry_run -> dismissed, no
    // undo), so a backed-out prompt must not move the report.
    const user = userEvent.setup();
    vi.spyOn(window, "prompt").mockReturnValue(null);
    renderReport();
    await screen.findByText("BobSin");

    await user.click(screen.getByRole("button", { name: /dismiss report/i }));

    expect(api.fetch.mock.calls.find(([path]) => String(path).includes("/dismiss"))).toBeUndefined();
  });

  it("dismisses with an empty note when the prompt is confirmed empty", async () => {
    // "" is a decision; null is a retreat. The two must not be conflated.
    const user = userEvent.setup();
    vi.spyOn(window, "prompt").mockReturnValue("");
    api.fetch.mockResolvedValue({ json: async () => REPORT });
    renderReport();
    await screen.findByText("BobSin");

    await user.click(screen.getByRole("button", { name: /dismiss report/i }));

    await waitFor(() => {
      expect(api.fetch.mock.calls.find(([path]) => String(path).includes("/dismiss"))).toBeTruthy();
    });
  });
});

describe("what a candidate row shows", () => {
  it("renders the description, address and ticket link the payload carries", async () => {
    // These fields were in the payload all along; a hand-copied Candidate
    // type hid them from the screen that decides what enters the graph.
    api.fetch.mockResolvedValue({
      json: async () => ({
        ...REPORT,
        candidates: [
          {
            draft: {
              name: "BobSin",
              venue: "Druso",
              address: "Via Galimberti 15",
              description: "Post-punk night with two openers",
              ticket_url: "https://dice.fm/event/bobsin",
              start_at: "2026-09-04T21:00:00+02:00",
            },
            source_url: "https://www.drusobg.it/",
            missing: [],
            dedup_status: "new",
          },
        ],
      }),
    });
    renderReport();

    expect(await screen.findByText("Via Galimberti 15")).toBeTruthy();
    expect(screen.getByText("Post-punk night with two openers")).toBeTruthy();
    expect(screen.getByRole("link", { name: "tickets" }).getAttribute("href")).toBe(
      "https://dice.fm/event/bobsin",
    );
  });
});
