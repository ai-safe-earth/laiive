/**
 * The promoter ground: the wordmark, tiled, at the edge of visible.
 *
 * It is what tells a promoter at a glance which of the two surfaces they are
 * on — the palettes are close cousins and the header lockup is nearly the
 * same. The consumer chat deliberately does not get it.
 *
 * DOM text rather than a background image: there is no wordmark asset, and an
 * SVG loaded as an image is an isolated document with no access to the page's
 * webfonts, so a data-URI tile would not render in Bebas at all. Rows instead
 * of one wrapping run, so the offset on odd rows can break the grid up.
 */

/**
 * Enough to cover a tall desktop vertically and an ultrawide horizontally —
 * 12 repeats ran out around 1600px and left the right half of a wide screen
 * bare ground. The parent clips whatever overflows.
 */
const ROWS = 22;
const PER_ROW = 24;

/**
 * Wide gaps, so the lettering reads as ground and never as a list of words.
 * Non-breaking spaces: a run of ordinary ones collapses to a single space.
 */
const WORD = `laiive${"\u00a0".repeat(6)}`;

export function ProWatermark() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 select-none overflow-hidden"
    >
      <div className="flex h-full flex-col justify-around">
        {Array.from({ length: ROWS }, (_, row) => (
          <span
            key={row}
            // 6% read as bare black from any normal distance; 11% is still
            // ground under cream body text but visibly laiive.
            className="whitespace-nowrap font-bebas text-[28px] leading-none tracking-[0.04em] text-pro-fg/[0.11]"
            // Half a word of offset on odd rows: a straight grid reads as a
            // table, a brick course reads as texture.
            style={{ transform: `translateX(${row % 2 === 0 ? "-2%" : "-9%"})` }}
          >
            {WORD.repeat(PER_ROW)}
          </span>
        ))}
      </div>
    </div>
  );
}
