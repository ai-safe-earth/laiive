import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

/** Pill field, 44px tall. Placeholder floor is `--ink-dim` — nothing dimmer. */
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-11 w-full rounded-full border border-field-border bg-field px-4",
        "text-[14.5px] text-foreground placeholder:text-ink-dim",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
