import type { ElementType, HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

/**
 * A live accent: a hole in the black window onto the one moving world that
 * styles/live-accents.css paints and useLiveAccents keeps aligned. Consumer
 * side only — pro screens, focus rings, amber and cyan stay flat.
 *
 * - `fill`: a fuchsia fill (primary button, FREE chip, account chip). Dark ink
 *   stays on top.
 * - `text`: a fuchsia Bebas headline word at 28px or more. Never body text.
 * - `mask`: a shape cut from a stencil — the mark or the saved glyph.
 */
const MASKS = { mark: "live-mark", saved: "live-saved" } as const;

type Look =
  | { variant?: "fill" | "text"; mask?: never }
  | { variant: "mask"; mask: keyof typeof MASKS };

/** The class string, for elements that cannot be swapped for the wrapper (Button). */
export function liveAccent(look: Look = {}): string {
  return cn(
    "live-accent",
    look.variant === "text" && "live-accent--text inline-block",
    look.variant === "mask" && ["live-accent--mask inline-block", MASKS[look.mask]],
  );
}

export function LiveAccent({
  as: Tag = "span",
  variant,
  mask,
  className,
  ...props
}: Look & { as?: ElementType } & HTMLAttributes<HTMLElement>) {
  const look = (variant === "mask" ? { variant, mask } : { variant }) as Look;
  return <Tag className={cn(liveAccent(look), className)} {...props} />;
}
