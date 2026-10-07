import { cn } from "@/lib/cn";

/**
 * The label voice: mono, small caps, 0.11em of tracking. One component, every
 * surface — the admin queue's column heads, the account settings, the saved
 * section rules and the submission form's fields were four copies of this
 * recipe that had already drifted apart on case and colour.
 *
 * `pro` defaults to true because the admin surface is by far the biggest caller
 * and is pro-themed throughout; the two consumer screens say so explicitly.
 *
 * `htmlFor` turns the span into a real <label> — the only thing that makes a
 * field's name reachable from its input, which is how the specs find them.
 */
export function Label({
  children,
  pro = true,
  htmlFor,
  required,
  missing,
}: {
  children: React.ReactNode;
  pro?: boolean;
  htmlFor?: string;
  /** Marks the field as one the form will not save without. */
  required?: boolean;
  /** Amber marks a field that still needs you; red one that is empty. */
  missing?: boolean;
}) {
  const Tag = htmlFor ? "label" : "span";
  return (
    <Tag
      htmlFor={htmlFor}
      className={cn(
        "font-mono text-xs uppercase tracking-[0.11em]",
        missing ? "text-destructive" : pro ? "text-pro-dim" : "text-muted-foreground",
      )}
    >
      {children}
      {required && (
        <span className={cn("ml-1", missing ? "text-destructive" : "text-secondary")}>*</span>
      )}
    </Tag>
  );
}
