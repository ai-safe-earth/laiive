import { cn } from "@/lib/cn";

/**
 * The brand icon set, one sprite, referenced rather than inlined:
 * `assets/brand/icons.svg` is copied to `public/brand/` unmodified, so the
 * artwork stays the file the brand owner ships and a fix there needs no code.
 *
 * Every symbol strokes `currentColor`, so colour comes from the parent's
 * text colour — never from a prop.
 */
export type IconName =
  | "saved"
  | "account"
  | "plus"
  | "mic"
  | "map"
  | "tickets"
  | "share"
  | "close"
  | "back"
  | "done"
  | "error"
  | "flyer"
  | "language"
  | "sign-out"
  | "attach"
  | "send"
  | "settings";

export function Icon({ name, className }: { name: IconName; className?: string }) {
  return (
    <svg className={cn("h-5 w-5 shrink-0", className)} aria-hidden="true" focusable="false">
      <use href={`/brand/icons.svg#${name}`} />
    </svg>
  );
}
