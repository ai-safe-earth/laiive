import { cn } from "@/lib/cn";

/**
 * The mark plus the wordmark, the one lockup the app uses. The PNG is the
 * original outline recoloured — never redrawn, never in a circle, never
 * gradiented (brand-rules.md, "Locked").
 */
export function Mark({ className, size = 27 }: { className?: string; size?: number }) {
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <img
        src="/brand/mark-fuchsia-alpha.png"
        alt=""
        width={size}
        height={size}
        className="block"
        style={{ width: size, height: size }}
      />
      <span
        className="font-bebas leading-none tracking-[0.04em] text-white"
        style={{ fontSize: Math.round(size * 0.9) }}
      >
        laiive
      </span>
    </span>
  );
}
