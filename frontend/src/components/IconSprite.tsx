// Vite inlines the file as a string at build time (`*?raw` is typed by
// vite/client, already referenced from vite-env.d.ts).
import sprite from "@brand/icons.svg?raw";

/**
 * The brand icon sprite, inlined into the document once.
 *
 * It used to be referenced across documents — `<use href="/brand/icons.svg#x">`
 * — which makes every icon wait on a second network round trip after the bundle
 * has already painted. The result was a visible flash of empty circles on first
 * load, worst on /pro where the composer is nothing but icons.
 *
 * Inlining costs ~4KB in the bundle and removes the request entirely, so the
 * icons are present in the first frame. `assets/brand/icons.svg` stays the one
 * source of truth: this imports the brand pack's own file, and the copy under
 * public/brand/ is still byte-identical — it is simply no longer on the render
 * path, and a fix to the artwork still needs no code change.
 *
 * The markup is the brand pack's, not user input, and its root <svg> already
 * carries `display:none`.
 */
export function IconSprite() {
  return <span aria-hidden="true" dangerouslySetInnerHTML={{ __html: sprite }} />;
}
