import { cn } from "@/lib/cn";

/**
 * The brand icon set, one sprite, inlined into the document by <IconSprite/>
 * at the app root — so these are same-document `#id` references and cost no
 * request. `assets/brand/icons.svg` is still the artwork the brand owner
 * ships, unmodified, and a fix there still needs no code change.
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
      <use href={`#${name}`} />
    </svg>
  );
}
