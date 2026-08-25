import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  useApprove,
  useDismiss,
  useReport,
  type Candidate,
  type WriteResult,
} from "@/api/admin";
import { A } from "@/admin/strings";
import { AdminButton, Badge, Empty, Label, Panel, statusTone } from "@/admin/ui";
import { Icon } from "@/components/Icon";

function startsAt(iso: string | null | undefined): string {
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

function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

const VERDICT_TONE = { new: "waiting", exists: "quiet", similar: "warn" } as const;

/** The writer refuses a draft with no venue, so say so before it is submitted. */
function refusable(candidate: Candidate): boolean {
  return candidate.missing.includes("venue");
}

function CandidateRow({
  candidate,
  index,
  checked,
  onToggle,
  result,
}: {
  candidate: Candidate;
  index: number;
  checked: boolean;
  onToggle: (index: number) => void;
  result?: WriteResult;
}) {
  const { draft } = candidate;
  const doomed = refusable(candidate);
  return (
    <tr className="border-b border-pro-border last:border-b-0 align-top">
      <td className="py-3 pl-4 pr-2">
        <input
          type="checkbox"
          checked={checked}
          onChange={() => onToggle(index)}
          aria-label={draft.name ?? `candidate ${index + 1}`}
          className="mt-1 h-4 w-4 accent-[hsl(var(--pro-accent))]"
        />
      </td>
      <td className="py-3 pr-3">
        <div className="text-[13.5px] leading-[1.35] text-pro-fg">
          {draft.name || "—"}
        </div>
        {draft.artists && draft.artists.length > 0 && (
          <div className="text-[12px] text-pro-dim">{draft.artists.join(", ")}</div>
        )}
        {/* The page swore this data was invisible for a while: the payload is
            the full protocol draft, but a hand-copied type hid everything
            below. A reviewer approving an event needs to see what was read. */}
        {draft.description && (
          <div className="max-w-md truncate pt-1 text-[11.5px] text-pro-dim" title={draft.description}>
            {draft.description}
          </div>
        )}
        {doomed && (
          <div className="pt-1 text-[11.5px] text-status-rejected">
            {A.report.willBeRefused}
          </div>
        )}
      </td>
      <td className="py-3 pr-3 text-[12.5px] text-pro-muted">
        {draft.venue || "—"}
        {draft.address && <div className="text-[11.5px] text-pro-dim">{draft.address}</div>}
      </td>
      <td className="py-3 pr-3 text-[12.5px] tabular-nums text-pro-muted">
        {startsAt(draft.start_at)}
      </td>
      <td className="py-3 pr-3 text-[12.5px]">
        {candidate.source_url ? (
          <a
            href={candidate.source_url}
            target="_blank"
            rel="noreferrer noopener"
            className="text-pro-accent underline underline-offset-2 hover:opacity-80"
          >
            {domainOf(candidate.source_url)}
          </a>
        ) : (
          <span className="text-pro-dim">—</span>
        )}
        {draft.ticket_url && (
          <div>
            <a
              href={draft.ticket_url}
              target="_blank"
              rel="noreferrer noopener"
              className="text-[11.5px] text-pro-dim underline underline-offset-2 hover:text-pro-accent"
            >
              tickets
            </a>
          </div>
        )}
      </td>
      <td className="py-3 pr-4">
        {result ? (
          <Badge tone={result.status === "created" ? "good" : "bad"}>
            {A.result[result.status] ?? result.status}
          </Badge>
        ) : (
          <Badge tone={VERDICT_TONE[candidate.dedup_status]}>
            {A.verdict[candidate.dedup_status]}
          </Badge>
        )}
      </td>
    </tr>
  );
}

export default function AdminReport() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, isError } = useReport(id);
  const approve = useApprove(id ?? "");
  const dismiss = useDismiss(id ?? "");
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const candidates = data?.candidates ?? [];
  const writeResults = data?.write_results ?? null;
  const resultByIndex = new Map((writeResults ?? []).map((r) => [r.index, r]));
  const settled = data ? data.status !== "dry_run" : false;

  const toggle = (index: number) =>
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });

  const selectAllNew = () =>
    setSelected(
      new Set(
        candidates
          .map((candidate, index) => ({ candidate, index }))
          .filter(({ candidate }) => candidate.dedup_status === "new" && !refusable(candidate))
          .map(({ index }) => index),
      ),
    );

  const onApprove = async () => {
    try {
      const outcome = await approve.mutateAsync([...selected].sort((a, b) => a - b));
      setSelected(new Set());
      toast.success(A.result.summary(outcome.created, outcome.results.length));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : A.report.failed);
    }
  };

  const onDismiss = async () => {
    const note = window.prompt(A.report.dismissPrompt);
    // Cancel/Esc returns null; an empty note is "" and still a decision. The
    // transition is one-way (dry_run -> dismissed, no undo endpoint), so a
    // backed-out prompt must not dismiss anything.
    if (note === null) return;
    try {
      await dismiss.mutateAsync(note);
      toast.success(A.status.dismissed);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : A.report.failed);
    }
  };

  return (
    <div className="min-h-[100dvh] bg-pro-bg">
      <header className="flex items-center justify-between gap-3 border-b border-pro-border px-5 py-4">
        <div className="flex min-w-0 items-baseline gap-3">
          <h1 className="truncate font-bebas text-[24px] leading-none tracking-[0.03em] text-pro-fg">
            {data?.city ?? A.title}
          </h1>
          {data && (
            <Badge tone={statusTone(data.status)}>
              {A.status[data.status] ?? data.status}
            </Badge>
          )}
        </div>
        <Link
          to="/admin"
          className="flex flex-none items-center gap-1.5 text-[13px] text-pro-muted transition-colors hover:text-pro-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pro-accent"
        >
          <Icon name="back" className="h-4 w-4" />
          {A.report.back}
        </Link>
      </header>

      <main className="mx-auto flex max-w-5xl flex-col gap-4 p-5">
        {isLoading && <Panel><Empty>{A.report.loading}</Empty></Panel>}
        {isError && <Panel><Empty>{A.report.failed}</Empty></Panel>}

        {data && candidates.length === 0 && <Panel><Empty>{A.report.empty}</Empty></Panel>}

        {data && candidates.length > 0 && (
          <>
            {!settled && (
              <div className="flex flex-wrap items-center gap-2">
                <AdminButton onClick={selectAllNew}>{A.report.selectAll}</AdminButton>
                <AdminButton onClick={() => setSelected(new Set())} disabled={selected.size === 0}>
                  {A.report.clear}
                </AdminButton>
                <span className="text-[12.5px] tabular-nums text-pro-dim">
                  {A.report.selected(selected.size)}
                </span>
                <span className="ml-auto flex gap-2">
                  <AdminButton variant="danger" onClick={onDismiss} disabled={dismiss.isPending}>
                    {dismiss.isPending ? A.report.dismissing : A.report.dismiss}
                  </AdminButton>
                  <AdminButton
                    variant="primary"
                    onClick={onApprove}
                    disabled={selected.size === 0 || approve.isPending}
                  >
                    {approve.isPending ? A.report.approving : A.report.approve}
                  </AdminButton>
                </span>
              </div>
            )}

            <Panel className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="border-b border-pro-border">
                      <th className="w-10 py-2 pl-4" />
                      <th className="py-2 pr-3 text-left"><Label>{A.report.colName}</Label></th>
                      <th className="py-2 pr-3 text-left"><Label>{A.report.colVenue}</Label></th>
                      <th className="py-2 pr-3 text-left"><Label>{A.report.colWhen}</Label></th>
                      <th className="py-2 pr-3 text-left"><Label>{A.report.colSource}</Label></th>
                      <th className="py-2 pr-4 text-left"><Label>{A.report.colVerdict}</Label></th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((candidate, index) => (
                      <CandidateRow
                        key={`${candidate.source_url}-${index}`}
                        candidate={candidate}
                        index={index}
                        checked={selected.has(index)}
                        onToggle={toggle}
                        result={resultByIndex.get(index)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </>
        )}
      </main>
    </div>
  );
}
