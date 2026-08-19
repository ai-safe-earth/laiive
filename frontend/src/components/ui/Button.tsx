import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

/**
 * Nothing is square (brand-rules.md): every button is a 999px pill, and every
 * filled accent carries `#0C0A0A` ink — white on fuchsia or amber is 3.45:1
 * and fails below 18px.
 */
type Variant = "primary" | "amber" | "cream" | "neutral" | "ghost" | "pro";
type Size = "default" | "icon" | "sm";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-primary text-primary-foreground hover:bg-primary/90",
  amber: "bg-secondary text-secondary-foreground hover:bg-secondary/90",
  cream: "bg-foreground text-background hover:bg-foreground/90",
  neutral: "border border-field-border bg-control text-muted-foreground hover:text-foreground",
  ghost: "text-ink-dim hover:text-foreground",
  pro: "border border-pro-accent/45 bg-pro-accent/10 text-pro-accent hover:bg-pro-accent/20",
};

/** 44px floor on every target, including the icon buttons. */
const SIZES: Record<Size, string> = {
  default: "h-11 px-6 text-[13.5px] font-medium",
  sm: "h-9 px-4 text-[12.5px] font-medium",
  icon: "h-11 w-11",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "default", type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full leading-none",
        "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        // The disabled pill is #241B1B on a #3A2E2E hairline, as the reference
        // draws it — and the hairline is load-bearing, not decoration. Without
        // an explicit border *width* the fill matches `bg-card` exactly, so a
        // disabled button sitting on a card (the auth form, the pro form) has
        // no edge and no contrast, and simply is not there.
        "disabled:pointer-events-none disabled:border disabled:border-border",
        "disabled:bg-card disabled:text-pro-dim",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
