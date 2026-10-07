import { forwardRef, type ButtonHTMLAttributes } from "react";
import { liveAccent } from "@/components/LiveAccent";
import { cn } from "@/lib/cn";

/**
 * Nothing is square (brand-rules.md): every button is a 999px pill, and every
 * filled accent carries `#0C0A0A` ink — white on fuchsia or amber is 3.45:1
 * and fails below 18px.
 */
type Variant = "primary" | "cream" | "neutral" | "ghost" | "cyan" | "proNeutral";
type Size = "default" | "icon";

const VARIANTS: Record<Variant, string> = {
  // Live, and only ever on the consumer side: every pro caller picks cream or
  // cyan. Hover brightens, because the world paints over any colour change.
  primary: cn("bg-primary text-primary-foreground hover:brightness-110", liveAccent()),
  cream: "bg-foreground text-background hover:bg-foreground/90",
  neutral: "border border-field-border bg-control text-muted-foreground hover:text-foreground",
  ghost: "text-ink-dim hover:text-foreground",
  cyan: "bg-pro-accent text-background hover:bg-pro-accent/90",
  proNeutral: "border border-pro-border bg-pro-control text-pro-muted hover:text-pro-fg",
};
// Three more outlines were declared here and never called: `pro` (a tinted cyan
// outline), and the two composer-mic outlines the mic stopped wearing when it
// moved inside the field and went `ghost`.

/**
/** 44px floor on every target, including the icon buttons. */
const SIZES: Record<Size, string> = {
  default: "h-11 px-6 text-md font-medium",
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
        // shrink-0 is what keeps a pill a pill. Flex items shrink by default,
        // and the composer's field asks for 100% of the row — so the mic and
        // the send were being squeezed to 38x44 ovals, under the 44px floor,
        // on every screen width. A button is never the thing that gives way.
        "inline-flex shrink-0 items-center justify-center gap-2 rounded-full leading-none",
        "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        // The disabled pill is #241B1B on a #3A2E2E hairline, as the reference
        // draws it — and the hairline is load-bearing, not decoration. Without
        // an explicit border *width* the fill matches `bg-card` exactly, so a
        // disabled button sitting on a card (the auth form, the pro form) has
        // no edge and no contrast, and simply is not there.
        "disabled:pointer-events-none disabled:border disabled:border-border",
        // bg-none drops a live accent's world, which would paint over the fill.
        "disabled:bg-card disabled:bg-none disabled:text-pro-dim",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
