import { describe, expect, it } from "vitest";
import config from "../tailwind.config";

/**
 * The scale is data, not logic, so this guards the one value in it that has a
 * behaviour attached: an input below 16px makes iOS zoom the page on focus and
 * never zoom back, which reads as the app breaking rather than as a font size.
 * `base` is what every input uses (brand-rules.md, Type).
 */
describe("the type scale", () => {
  const sizes = config.theme?.fontSize as Record<string, string>;
  const px = (token: string) => parseFloat(sizes[token] ?? "") * 16;

  it("keeps inputs at or above the 16px iOS zoom floor", () => {
    expect(px("base")).toBeGreaterThanOrEqual(16);
  });

  it("rises monotonically, so a bigger token is never smaller type", () => {
    const order = ["2xs", "xs", "sm", "md", "base", "lg", "xl", "2xl", "3xl", "4xl"];
    const values = order.map(px);
    expect(values).toEqual([...values].sort((a, b) => a - b));
  });
});
