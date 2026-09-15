import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

/**
 * The field skin, shared by this component and the composer's textarea — the
 * two would otherwise drift, and they sit on the same row. Shape (radius,
 * height, padding) belongs to the caller: the composer's field grows.
 */
export const FIELD =
  "w-full min-w-0 border border-field-border bg-field text-base text-foreground " +
  "placeholder:text-ink-dim focus-visible:outline-none focus-visible:ring-2 " +
  "focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

/**
 * The promoter field, filled: the consumer field tokens sit almost exactly on
 * the pro ground, so an unfilled pill reads as a hole in the watermark.
 * Exported for the two native controls (`<select>`, `<textarea>`) that share
 * the skin but not the component.
 */
export const PRO_FIELD =
  "border-pro-border bg-pro-control text-pro-fg placeholder:text-pro-dim focus-visible:ring-pro-accent";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  tone?: "pro";
}

/** Pill field, 44px tall. Placeholder floor is `--ink-dim` — nothing dimmer. */
export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, tone, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        FIELD,
        "flex h-11 rounded-full px-4",
        tone === "pro" && PRO_FIELD,
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
