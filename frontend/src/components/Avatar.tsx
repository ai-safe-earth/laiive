import { Icon } from "@/components/Icon";
import { cn } from "@/lib/cn";

/**
 * Initials for the account chip.
 *
 * The display name first, then the local part of the email — `oscar.arroyo@…`
 * reads as "OA" because the separators become spaces before splitting, which
 * is the shape most addresses take.
 *
 * One word gives one letter. "CH" for "Cher" is a guess about a name we were
 * given in full, and a wrong guess about somebody's name is worse than a
 * smaller chip.
 */
export function initials(
  displayName: string | null | undefined,
  email: string | null | undefined,
): string {
  const source =
    displayName?.trim() || email?.split("@")[0]?.replace(/[._+-]+/g, " ").trim() || "";
  const words = source.split(/\s+/).filter(Boolean);
  const head = words[0];
  const tail = words[words.length - 1];
  if (!head || !tail) return "";
  // Spread, not [0]: indexing a string cuts an astral character in half and
  // renders a replacement box, so one emoji or a rarer CJK glyph in a display
  // name would put "&#65533;" in the header.
  // ponytail: code points, not graphemes — a ZWJ sequence still splits.
  // Intl.Segmenter if that ever turns up in a real name.
  const first = [...head][0] ?? "";
  const last = words.length > 1 ? ([...tail][0] ?? "") : "";
  // Locale-aware rather than the ascii table: on a browser set to Turkish or
  // Azeri a dotted "i" becomes "İ". The host locale decides, not the app's.
  return (first + last).toLocaleUpperCase();
}

/**
 * The signed-in chip. aria-hidden because every caller already labels the
 * control it sits in — announcing "OA" after "account" is just noise.
 */
export function Avatar({
  displayName,
  email,
  pro,
  className,
}: {
  displayName: string | null | undefined;
  email: string | null | undefined;
  pro: boolean;
  className?: string;
}) {
  const label = initials(displayName, email);
  if (!label) return <Icon name="account" />;
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-mono text-xs leading-none",
        // No tracking: two characters plus a letter-space sit off-centre in a
        // circle. --primary is brand-and-free only, --pro-accent is the badge.
        pro ? "border border-pro-border bg-pro-control text-pro-fg" : "bg-muted text-foreground",
        className,
      )}
    >
      {label}
    </span>
  );
}
