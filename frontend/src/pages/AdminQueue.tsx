import { useState } from "react";
import { Link } from "react-router-dom";
import { useReports, type ReportSummary } from "@/api/admin";
import { A } from "@/admin/strings";
import { AdminButton, Badge, Empty, Label, Panel, statusTone } from "@/admin/ui";
import { Icon } from "@/components/Icon";

/** Sweeps only: a backfill report has no candidates to review. */
const WAITING = "dry_run";

function when(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function num(stats: ReportSummary["stats"], key: string): number | null {
  const value = stats?.[key];
  return typeof value === "number" ? value : null;
}

function Row({ report }: { report: ReportSummary }) {
  const isSweep = report.kind === "sweep";
  const found = num(report.stats, "new");
  const credits = num(report.stats, "tavily_credits");
  return (
    <Link
      to={`/admin/reports/${report.id}`}
      className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 border-b border-pro-border px-5 py-4 transition-colors last:border-b-0 hover:bg-pro-elevated focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pro-accent sm:grid-cols-[1.4fr_.8fr_.6fr_.6fr_auto]"
    >
      <span className="truncate font-bebas text-[17px] leading-none tracking-[0.03em] text-pro-fg">
        {report.city ?? A.queue.backfillKind}
      </span>
      <span className="text-[12.5px] tabular-nums text-pro-muted">{when(report.created_at)}</span>
      <span className="hidden text-[12.5px] tabular-nums text-pro-muted sm:block">
        {isSweep && found !== null ? `${found} new` : "—"}
      </span>
      <span className="hidden text-[12.5px] tabular-nums text-pro-dim sm:block">
        {credits !== null ? `${credits} cr` : "—"}
      </span>
      <Badge tone={statusTone(report.status)}>{A.status[report.status] ?? report.status}</Badge>
    </Link>
  );
}

export default function AdminQueue() {
  const [onlyWaiting, setOnlyWaiting] = useState(true);
  const { data, isLoading, isError, refetch } = useReports(onlyWaiting ? WAITING : "");

  return (
    <div className="min-h-[100dvh] bg-pro-bg">
      <header className="flex items-center justify-between gap-3 border-b border-pro-border px-5 py-4">
        <div className="flex items-baseline gap-3">
          <h1 className="font-bebas text-[24px] leading-none tracking-[0.03em] text-pro-fg">
            {A.title}
          </h1>
          <Label>{A.queue.heading}</Label>
        </div>
        <Link
          to="/"
          className="flex items-center gap-1.5 text-[13px] text-pro-muted transition-colors hover:text-pro-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pro-accent"
        >
          <Icon name="back" className="h-4 w-4" />
          {A.nav.back}
        </Link>
      </header>

      <main className="mx-auto flex max-w-4xl flex-col gap-4 p-5">
        <div className="flex gap-2">
          <AdminButton
            variant={onlyWaiting ? "primary" : "quiet"}
            onClick={() => setOnlyWaiting(true)}
            aria-pressed={onlyWaiting}
          >
            {A.queue.waiting}
          </AdminButton>
          <AdminButton
            variant={onlyWaiting ? "quiet" : "primary"}
            onClick={() => setOnlyWaiting(false)}
            aria-pressed={!onlyWaiting}
          >
            {A.queue.all}
          </AdminButton>
        </div>

        <Panel className="overflow-hidden">
          {isLoading && <Empty>{A.queue.loading}</Empty>}
          {isError && (
            <Empty>
              <p className="mb-3">{A.queue.failed}</p>
              <AdminButton onClick={() => refetch()}>{A.queue.retry}</AdminButton>
            </Empty>
          )}
          {data?.length === 0 && (
            <Empty>{onlyWaiting ? A.queue.empty : A.queue.emptyAll}</Empty>
          )}
          {data?.map((report) => <Row key={report.id} report={report} />)}
        </Panel>
      </main>
    </div>
  );
}
