import { A } from "@/admin/strings";
import { Badge, Empty, Label, Panel, type Tone } from "@/admin/ui";
import { useStats, type SchedulerDeployment, type SearchStats } from "@/api/admin";
import { Icon } from "@/components/Icon";
import { cn } from "@/lib/cn";

/**
 * The numbers above the queue: is discovery running, what is waiting, what is
 * it costing, what is it yielding. One `useStats` call feeds all of it — the
 * gateway rate limit is per-user across /api/*, and a dashboard that browses
 * its own sections into a 429 is worse than none.
 *
 * Charts are plain HTML tracks in the one data hue (`--pro-accent`, contrast-
 * checked against the pro surface); amber and green appear only as labelled
 * status, never as series.
 */

function when(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function Tile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "attention";
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-[14px] border border-pro-border bg-pro-card px-4 py-3">
      <Label>{label}</Label>
      <span
        className={cn(
          "truncate font-bebas text-[26px] leading-none tracking-[0.02em]",
          tone === "attention" ? "text-status-attention" : "text-pro-fg",
        )}
      >
        {value}
      </span>
      {hint && <span className="font-mono text-[10px] text-pro-dim">{hint}</span>}
    </div>
  );
}

/** Small columns, one hue, values on hover — a shape, not a table. */
function Columns({
  items,
  ariaLabel,
}: {
  items: { key: string; label?: string; value: number; title: string }[];
  ariaLabel: string;
}) {
  const max = Math.max(...items.map((item) => item.value), 1);
  return (
    <div className="flex items-end gap-1.5" role="img" aria-label={ariaLabel}>
      {items.map((item) => (
        <div
          key={item.key}
          className="flex min-w-0 flex-1 flex-col items-center gap-1"
          title={item.title}
        >
          <div
            className="w-full rounded-t-[4px] bg-pro-accent"
            style={{ height: `${Math.max((item.value / max) * 56, 2)}px` }}
          />
          {item.label !== undefined && (
            <span className="font-mono text-[9px] leading-none text-pro-dim">
              {item.label}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

/** Horizontal bar rows: identity in text ink, magnitude in the data hue. */
function SourceRows({ top }: { top: SearchStats["sources"]["top"] }) {
  const max = Math.max(...top.map((source) => source.candidates_new), 1);
  const tone: Record<string, Tone> = { trusted: "good", blocked: "bad" };
  return (
    <div className="flex flex-col gap-2">
      {top.map((source) => (
        <div
          key={source.domain}
          className="grid grid-cols-[minmax(0,1.2fr)_2fr_auto] items-center gap-3"
          title={`${source.domain}: ${source.candidates_new} new candidates · yield ${source.yield}`}
        >
          <span className="flex min-w-0 items-center gap-1.5">
            <span className="truncate text-[12.5px] text-pro-fg">{source.domain}</span>
            {tone[source.status] && (
              <Badge tone={tone[source.status]!}>{source.status}</Badge>
            )}
          </span>
          <div className="h-2 overflow-hidden rounded-full bg-pro-elevated">
            <div
              className="h-full rounded-full bg-pro-accent"
              style={{ width: `${(source.candidates_new / max) * 100}%` }}
            />
          </div>
          <span className="font-mono text-[11px] tabular-nums text-pro-muted">
            {source.candidates_new}
          </span>
        </div>
      ))}
    </div>
  );
}

function Scheduler({ scheduler }: { scheduler: SearchStats["scheduler"] }) {
  // "Nothing is polling" strikes every next-run; a single non-READY
  // deployment strikes only its own row; a Prefect blip strikes nothing.
  const nothingPolling = scheduler.reason === "stale_runs";
  return (
    <Panel className="flex flex-col gap-3 p-5">
      <Label>{A.stats.upcoming}</Label>
      {/* "None registered" is only a truth we can claim after asking. */}
      {scheduler.deployments.length === 0 && (
        <Empty>
          {scheduler.configured ? A.stats.noDeployments : A.stats.schedulerUnconfigured}
        </Empty>
      )}
      {scheduler.deployments.map((deployment: SchedulerDeployment) => (
        <div
          key={deployment.name}
          className="grid grid-cols-[1.2fr_auto] items-baseline gap-x-4 gap-y-0.5 sm:grid-cols-[1.2fr_.6fr_1fr_auto]"
        >
          <span className="truncate text-[13px] text-pro-fg">{deployment.name}</span>
          <span className="hidden font-mono text-[11px] text-pro-dim sm:block">
            {deployment.cron ?? "—"}
          </span>
          {/* A next-run time nothing will execute is not a time, it is a trap. */}
          <span
            className={cn(
              "font-mono text-[11px] tabular-nums",
              nothingPolling || deployment.status !== "READY"
                ? "text-pro-dim line-through"
                : "text-pro-muted",
            )}
          >
            {when(deployment.next_run)}
          </span>
          <Badge tone={deployment.last_run_state === "COMPLETED" ? "good" : "quiet"}>
            {deployment.last_run_state?.toLowerCase() ?? A.stats.neverRan}
          </Badge>
        </div>
      ))}
    </Panel>
  );
}

export function AdminStats() {
  const { data, isLoading, isError } = useStats();

  if (isLoading) return null; // the queue below is the screen's real job
  if (isError || !data) {
    return (
      <Panel>
        <Empty>{A.stats.failed}</Empty>
      </Panel>
    );
  }

  const { reports, credits, sources, queries, graph, scheduler } = data;
  const sweeps = reports.recent
    .filter((report) => report.kind === "sweep")
    .slice(0, 12)
    .reverse();
  const overBudget = credits.projected_month_end > credits.budget;

  // The amber claim must match the evidence: stale runs (or a NOT_READY
  // deployment) prove nothing is polling; a blip only proves we cannot see.
  const schedulerClaim =
    scheduler.reason === "stale_runs" || scheduler.reason === "not_ready"
      ? A.stats.schedulerDown
      : scheduler.reason === "unreachable"
        ? A.stats.prefectUnreachable
        : null;

  return (
    <div className="flex flex-col gap-4">
      {scheduler.configured && schedulerClaim && (
        <div
          role="status"
          className="flex items-center gap-2.5 rounded-[14px] border border-status-attention/45 bg-status-attention/[0.12] px-4 py-3 text-[13px] leading-[1.4] text-status-attention"
        >
          <Icon name="error" className="h-4 w-4 flex-none" />
          {schedulerClaim}
        </div>
      )}
      {!scheduler.configured && <Label>{A.stats.schedulerUnconfigured}</Label>}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile
          label={A.stats.waitingReports}
          value={String(reports.backlog.count)}
          hint={A.stats.waitingCandidates(reports.backlog.candidates)}
        />
        <Tile
          label={A.stats.creditsMonth}
          value={`${credits.month_to_date} / ${credits.budget}`}
          hint={A.stats.projected(credits.projected_month_end)}
          tone={overBudget ? "attention" : undefined}
        />
        <Tile
          label={A.stats.graphEvents}
          value={graph.error ? "—" : String(graph.events ?? "—")}
          hint={graph.error ? A.stats.graphUnreachable : A.stats.artistsVenues(graph.artists ?? 0, graph.venues ?? 0)}
        />
        <Tile
          label={A.stats.quality}
          value={
            graph.quality?.start_time_known_pct != null
              ? `${graph.quality.start_time_known_pct}%`
              : "—"
          }
          hint={
            graph.quality?.price_known_pct != null
              ? A.stats.priceKnown(graph.quality.price_known_pct)
              : undefined
          }
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Panel className="flex flex-col gap-3 p-5">
          <Label>{A.stats.creditsWeekly}</Label>
          <Columns
            ariaLabel={A.stats.creditsWeekly}
            items={credits.by_week.map(({ week, credits: spent }) => ({
              key: week,
              label: week.slice(-3),
              value: spent,
              title: `${week}: ${spent} credits`,
            }))}
          />
        </Panel>
        <Panel className="flex flex-col gap-3 p-5">
          <Label>{A.stats.perSweep}</Label>
          {sweeps.length === 0 ? (
            <Empty>{A.stats.noSweeps}</Empty>
          ) : (
            <Columns
              ariaLabel={A.stats.perSweep}
              items={sweeps.map((report) => ({
                key: report.id,
                value: Number(report.stats?.new ?? 0),
                title: `${report.city ?? "sweep"} · ${when(report.created_at)}: ${report.stats?.new ?? 0} new`,
              }))}
            />
          )}
        </Panel>
        {(graph.events_last_30d?.length ?? 0) > 0 && (
          <Panel className="flex flex-col gap-3 p-5">
            <Label>{A.stats.eventsDaily}</Label>
            <Columns
              ariaLabel={A.stats.eventsDaily}
              items={graph.events_last_30d!.map((entry) => ({
                key: entry.day,
                value: entry.count,
                title: `${entry.day}: ${entry.count}`,
              }))}
            />
          </Panel>
        )}
      </div>

      {sources.top.length > 0 && (
        <Panel className="flex flex-col gap-3 p-5">
          <span className="flex items-baseline justify-between">
            <Label>{A.stats.sources}</Label>
            <span className="font-mono text-[10px] text-pro-dim">
              {A.stats.queriesStanding(queries.standing.length, queries.trial.length)}
            </span>
          </span>
          <SourceRows top={sources.top.slice(0, 8)} />
        </Panel>
      )}

      <Scheduler scheduler={scheduler} />
    </div>
  );
}
