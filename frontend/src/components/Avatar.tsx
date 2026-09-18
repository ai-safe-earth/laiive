import { Icon } from "@/components/Icon";
import { cn } from "@/lib/cn";

/**
 * Initials for the account chip.
 *
 * The display name first, then the local part of the email — `oscar.arroyo@…`
 * reads as "OA" because the separators become spaces before splitting, which
 * is the shape most addresses take.
 *
 * Always two characters. One word gives its first two — "Cher" reads as "CH",
 * `arroscar@…` as "AR" — because a single letter in a coloured circle reads as
 * an unfinished chip rather than a monogram.
 */
export function initials(
  displayName: string | null | undefined,
  email: string | null | undefined,
): string {
  // Separators become spaces in both sources, not just the email: the second
  // character of a single word is taken raw, and "O'Brien" as "O'" or "T-Pain"
  // as "T-" is punctuation in a monogram. Apostrophes included, both shapes —
  // stage names and Irish surnames are the expected input in an events app.
  const source = (displayName?.trim() || email?.split("@")[0] || "")
    .replace(/[._+\-'’]+/g, " ")
    .trim();
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
  // Two words give one letter each; a single word gives its own second
  // character, which is a fact about the name rather than a guess at a surname.
  const last = words.length > 1 ? ([...tail][0] ?? "") : ([...head][1] ?? "");
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
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-full font-mono text-sm font-medium leading-none",
        // No tracking: two characters plus a letter-space sit off-centre in a
        // circle. The chip carries its surface's accent — and dark ink on it,
        // never cream: white on fuchsia is 3.45:1. The circle is 36px, not the
        // original 32: two characters at 17px no longer sit comfortably in it.
        pro ? "bg-pro-accent text-background" : "bg-primary text-primary-foreground",
        className,
      )}
    >
      {label}
    </span>
  );
}
