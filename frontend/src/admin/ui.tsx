/**
 * The handful of primitives an admin surface needs and the app does not have.
 *
 * Built on the `status.*` and `pro.*` tokens, which brand-tokens.css already
 * declared and nothing used — review / published / attention / rejected /
 * draft is a moderation vocabulary, and this is the moderation surface.
 */
import { cn } from "@/lib/cn";

/** Small-caps label voice, same recipe as Account.tsx's Label. */
export function Label({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "font-mono text-[11px] uppercase tracking-[0.11em] text-pro-dim",
        className,
      )}
    >
      {children}
    </span>
  );
}

const TONES = {
  waiting: "border-status-review/45 bg-status-review/[0.12] text-status-review",
  good: "border-status-published/45 bg-status-published/[0.12] text-status-published",
  warn: "border-status-attention/45 bg-status-attention/[0.12] text-status-attention",
  bad: "border-status-rejected/45 bg-status-rejected/[0.12] text-status-rejected",
  quiet: "border-pro-border bg-pro-elevated text-pro-dim",
} as const;

export type Tone = keyof typeof TONES;

export function Badge({ tone = "quiet", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex flex-none items-center rounded-full border px-2 py-[3px]",
        "font-mono text-[9.5px] uppercase leading-none tracking-[0.11em]",
        TONES[tone],
      )}
    >
      {children}
    </span>
  );
}

/** Report status → tone. Kept in one place so the queue and the detail agree. */
export function statusTone(status: string): Tone {
  if (status === "dry_run" || status === "running") return "waiting";
  if (status === "approved" || status === "done") return "good";
  if (status === "failed") return "bad";
  return "quiet";
}

export function Panel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "rounded-[20px] border border-pro-border bg-pro-card",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function AdminButton({
  children,
  variant = "quiet",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "quiet" | "danger" }) {
  const styles = {
    primary: "bg-pro-accent text-pro-bg hover:opacity-90 disabled:opacity-40",
    quiet: "border border-pro-border text-pro-fg hover:bg-pro-elevated disabled:opacity-40",
    danger: "border border-status-rejected/50 text-status-rejected hover:bg-status-rejected/10 disabled:opacity-40",
  }[variant];
  return (
    <button
      {...props}
      className={cn(
        "rounded-full px-4 py-2 text-[13px] font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pro-accent",
        "disabled:cursor-not-allowed",
        styles,
        props.className,
      )}
    >
      {children}
    </button>
  );
}

/** Says what is absent and why, never just "no data". */
export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-6 py-14 text-center text-[13.5px] leading-[1.5] text-pro-muted">
      {children}
    </div>
  );
}
