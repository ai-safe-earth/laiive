import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminStats } from "./AdminStats";
import { A } from "./strings";
import type { SearchStats } from "@/api/admin";

const api = vi.hoisted(() => ({ fetch: vi.fn() }));
vi.mock("@/api/client", () => ({
  apiFetch: api.fetch,
  ApiError: class extends Error {},
}));

function payload(overrides: Partial<SearchStats> = {}): SearchStats {
  return {
    generated_at: "2026-08-25T12:00:00+00:00",
    window: 200,
    reports: {
      by_status: { dry_run: 12, approved: 20 },
      backlog: { count: 12, candidates: 180, oldest_created_at: "2026-08-20T07:00:00+00:00" },
      recent: [
        {
          id: "r1",
          city: "Bergamo",
          kind: "sweep",
          status: "dry_run",
          created_at: "2026-08-25T07:00:00+00:00",
          approved_at: null,
          stats: { new: 33 },
          write_summary: {},
        },
      ],
    },
    credits: {
      month_to_date: 435,
      budget: 1000,
      projected_month_end: 480,
      by_week: [
        { week: "2026-W34", credits: 11 },
        { week: "2026-W35", credits: 6 },
      ],
    },
    sources: {
      counts_by_status: { trusted: 3, candidate: 14 },
      top: [
        {
          domain: "dastebergamo.com",
          status: "trusted",
          pages: 4,
          yield: 0.9,
          candidates_new: 21,
          events_written: 18,
        },
      ],
    },
    queries: { standing: [], trial: [], retired_count: 0 },
    graph: {
      events: 128,
      venues: 35,
      artists: 90,
      events_last_30d: [],
      quality: {
        start_time_known_pct: 76,
        price_known_pct: 41,
      },
    },
    scheduler: {
      configured: true,
      alive: true,
      reason: null,
      deployments: [
        {
          name: "bergamo-province-weekly",
          status: "READY",
          cron: "0 7 * * 2",
          next_run: "2026-09-01T07:00:00+00:00",
          last_run_state: "COMPLETED",
          last_run_at: "2026-08-25T07:00:04+00:00",
        },
      ],
    },
    ...overrides,
  };
}

function renderStats(body: SearchStats) {
  api.fetch.mockResolvedValue({ json: async () => body } as Response);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <AdminStats />
    </QueryClientProvider>,
  );
}

beforeEach(() => api.fetch.mockReset());

describe("the numbers above the queue", () => {
  it("answers the whole screen with one request", async () => {
    renderStats(payload());
    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(api.fetch).toHaveBeenCalledTimes(1);
    expect(api.fetch.mock.calls[0]![0]).toBe("/api/admin/search/stats");
  });

  it("shows the credit budget line and the projection", async () => {
    renderStats(payload());
    expect(await screen.findByText("435 / 1000")).toBeInTheDocument();
    expect(screen.getByText(A.stats.projected(480))).toBeInTheDocument();
  });

  it("warns when schedules are registered but nothing is polling", async () => {
    renderStats(
      payload({
        scheduler: {
          configured: true,
          alive: false,
          reason: "stale_runs",
          stale_runs: 1,
          deployments: [
            {
              name: "bergamo-province-weekly",
              status: "READY",
              cron: "0 7 * * 2",
              next_run: "2026-09-01T07:00:00+00:00",
              last_run_state: null,
              last_run_at: null,
            },
          ],
        },
      }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(/nothing is polling/);
    // The next-run time renders dead, not as a promise.
    expect(screen.getByText(/Sep/).className).toContain("line-through");
  });

  it("stays quiet when the scheduler is alive", async () => {
    renderStats(payload());
    await screen.findByText("435 / 1000");
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByText(/Sep/).className).not.toContain("line-through");
  });

  it("says so when the scheduler was never configured", async () => {
    renderStats(
      payload({
        scheduler: {
          configured: false,
          alive: false,
          reason: "unconfigured",
          deployments: [],
        },
      }),
    );
    // Twice on purpose: the top-of-page note and the rounds panel's empty
    // state both say it rather than claiming "none registered" unasked.
    expect(
      await screen.findAllByText(A.stats.schedulerUnconfigured),
    ).toHaveLength(2);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("marks an unreachable graph instead of faking a zero", async () => {
    renderStats(payload({ graph: { error: "paused" } }));
    expect(await screen.findByText(A.stats.graphUnreachable)).toBeInTheDocument();
  });

  it("draws the sources as labelled bars, not a colour code", async () => {
    renderStats(payload());
    expect(await screen.findByText("dastebergamo.com")).toBeInTheDocument();
    expect(screen.getByText("21")).toBeInTheDocument();
    expect(screen.getByText("trusted")).toBeInTheDocument();
  });
});
