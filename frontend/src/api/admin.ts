/**
 * The admin surface, all of it through the gateway.
 *
 * Never `supabase.from(...)`: `search_reports` has RLS on with no user
 * policies, so it is service-role only and a browser token cannot read a row
 * of it. The gateway's `/api/admin/search/*` prefix is already gated on
 * `requireRole("admin")`, which is why none of this needs a new route.
 *
 * Note the gateway rate limit applies per user across every `/api/*` path
 * (admins get a higher cap, not an exemption) — so these queries are
 * deliberately not on a refetch interval, and the report list is not
 * re-fetched to render a detail page.
 */
import type { EventDraft } from "@shared/protocol";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";

const BASE = "/api/admin/search";

export type ReportStatus =
  | "running"
  | "dry_run"
  | "approved"
  | "dismissed"
  | "failed"
  | "done";

export interface ReportSummary {
  id: string;
  city: string | null;
  status: ReportStatus;
  kind: "sweep" | "backfill";
  error: string | null;
  /** Sweep counters — shape differs by `kind`, so every read is optional. */
  stats: Record<string, number | string | null> | null;
  created_at: string;
  approved_at: string | null;
}

export interface Candidate {
  /**
   * The full protocol draft, not a subset: the search service serializes
   * `EventDraft.model_dump()` and approve rehydrates the same model, so a
   * hand-copied field list here only hides data the reviewer needs (it hid
   * address, description and ticket_url until it did exactly that).
   */
  draft: Partial<EventDraft>;
  source_url: string;
  missing: string[];
  dedup_status: "new" | "exists" | "similar";
  matched_name?: string | null;
  similarity?: number | null;
}

export interface ReportDetail extends ReportSummary {
  candidates: Candidate[];
  write_results: WriteResult[] | null;
  /** Only present once migration 20260823000014 is applied. */
  reviewed_at?: string | null;
  review_note?: string | null;
}

export interface WriteResult {
  index: number;
  status: "created" | "duplicate" | "invalid" | "error";
  uid: string | null;
  name: string | null;
  message: string;
  warnings: string[];
}

export interface SchedulerDeployment {
  name: string;
  status: string;
  cron: string | null;
  next_run: string | null;
  last_run_state: string | null;
  last_run_at: string | null;
}

/** The one-call dashboard payload — GET /api/admin/search/stats. */
export interface SearchStats {
  generated_at: string;
  window: number;
  reports: {
    by_status: Record<string, number>;
    backlog: { count: number; candidates: number; oldest_created_at: string | null };
    recent: {
      id: string;
      city: string | null;
      kind: string;
      status: string;
      created_at: string;
      approved_at: string | null;
      stats: Record<string, unknown>;
      write_summary: Record<string, number>;
    }[];
  };
  credits: {
    month_to_date: number;
    budget: number;
    projected_month_end: number;
    by_week: { week: string; credits: number }[];
  };
  sources: {
    counts_by_status: Record<string, number>;
    top: {
      domain: string;
      status: string;
      pages: number;
      yield: number;
      candidates_new: number;
      events_written: number;
    }[];
  };
  queries: {
    standing: { template: string; runs: number; candidates_new: number }[];
    trial: { template: string; runs: number; candidates_new: number }[];
    retired_count: number;
  };
  graph: {
    error?: string;
    events?: number;
    venues?: number;
    artists?: number;
    events_last_30d?: { day: string; count: number }[];
    quality?: {
      start_time_known_pct: number | null;
      price_known_pct: number | null;
    };
  };
  scheduler: {
    configured: boolean;
    alive: boolean;
    /** Why alive is false — the banner must not claim "nothing is polling"
     *  for a Prefect blip or an empty workspace. */
    reason?:
      | "unconfigured"
      | "unreachable"
      | "no_deployments"
      | "stale_runs"
      | "not_ready"
      | null;
    error?: string;
    stale_runs?: number;
    deployments: SchedulerDeployment[];
  };
}

export const adminKeys = {
  reports: (status: string) => ["admin", "reports", status] as const,
  report: (id: string) => ["admin", "report", id] as const,
  stats: ["admin", "stats"] as const,
};

export function useStats() {
  return useQuery({
    queryKey: adminKeys.stats,
    // One call answers the whole dashboard; a minute of staleness is nothing
    // for numbers that move once a sweep.
    staleTime: 60_000,
    queryFn: async (): Promise<SearchStats> => {
      const response = await apiFetch(`${BASE}/stats`);
      return (await response.json()) as SearchStats;
    },
  });
}

export function useReports(status: string) {
  return useQuery({
    queryKey: adminKeys.reports(status),
    queryFn: async (): Promise<ReportSummary[]> => {
      const query = status ? `?status=${encodeURIComponent(status)}&limit=100` : "?limit=100";
      const response = await apiFetch(`${BASE}/reports${query}`);
      const body = (await response.json()) as { reports: ReportSummary[] };
      return body.reports;
    },
  });
}

export function useReport(id: string | undefined) {
  return useQuery({
    queryKey: adminKeys.report(id ?? "none"),
    enabled: Boolean(id),
    queryFn: async (): Promise<ReportDetail> => {
      const response = await apiFetch(`${BASE}/reports/${id}`);
      return (await response.json()) as ReportDetail;
    },
  });
}

export function useApprove(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (indices: number[]) => {
      const response = await apiFetch(`${BASE}/reports/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({ indices }),
      });
      return (await response.json()) as {
        report_id: string;
        created: number;
        results: WriteResult[];
        warnings: string[];
      };
    },
    // The report's own status changed, and so did the queue it was in.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.report(id) });
      queryClient.invalidateQueries({ queryKey: ["admin", "reports"] });
    },
  });
}

export function useDismiss(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (note: string) => {
      const response = await apiFetch(`${BASE}/reports/${id}/dismiss`, {
        method: "POST",
        body: JSON.stringify({ note }),
      });
      return (await response.json()) as { report_id: string; status: string };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.report(id) });
      queryClient.invalidateQueries({ queryKey: ["admin", "reports"] });
    },
  });
}
