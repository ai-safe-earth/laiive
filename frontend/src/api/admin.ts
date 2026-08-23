/**
 * The admin surface, all of it through the gateway.
 *
 * Never `supabase.from(...)`: `search_reports` has RLS on with no user
 * policies, so it is service-role only and a browser token cannot read a row
 * of it. The gateway's `/api/admin/search/*` prefix is already gated on
 * `requireRole("admin")`, which is why none of this needs a new route.
 *
 * Note the gateway rate limit is 60 requests a minute per user across every
 * `/api/*` path, with no admin exemption — so these queries are deliberately
 * not on a refetch interval, and the report list is not re-fetched to render a
 * detail page.
 */
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
  draft: {
    name?: string | null;
    artists?: string[];
    start_at?: string | null;
    venue?: string | null;
    city?: string | null;
    price_min?: number | null;
    price_currency?: string | null;
    genre?: string | null;
  };
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

export const adminKeys = {
  reports: (status: string) => ["admin", "reports", status] as const,
  report: (id: string) => ["admin", "report", id] as const,
};

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
