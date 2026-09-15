import { cn } from "@/lib/cn";

/**
 * The mark plus the wordmark, the one lockup the app uses. The PNG is the
 * original outline recoloured — never redrawn, never in a circle, never
 * gradiented (brand-rules.md, "Locked").
 *
 * `size` is px, so the lockup does not follow the type scale and has to be
 * moved by hand when that moves: these numbers carry the 2026-09-16 lift,
 * 1.25x on the consumer surfaces and 1.125x on the promoter ones, which run
 * their type nine tenths the size.
 */
export function Mark({ className, size = 34 }: { className?: string; size?: number }) {
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
