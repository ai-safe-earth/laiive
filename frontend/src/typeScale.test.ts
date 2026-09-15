import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import config from "../tailwind.config";

/**
 * The scale is data, not logic, so this guards the two values in it that have
 * behaviour attached. An input below 16px makes iOS zoom the page on focus and
 * never zoom back, which reads as the app breaking rather than as a font size —
 * and `base` is what every input uses (brand-rules.md, Type). The promoter and
 * admin surfaces run the same tokens through `--type-scale`, so their inputs
 * have to clear that floor on the multiplied value, not the nominal one.
 */
describe("the type scale", () => {
  const sizes = config.theme?.fontSize as Record<string, string>;

  /** Each value is `calc(<n>rem * var(--type-scale, 1))`. */
  const px = (token: string) => {
    const rem = /(\d*\.?\d+)rem/.exec(sizes[token] ?? "")?.[1];
    if (!rem) throw new Error(`${token} is not a rem value: ${sizes[token]}`);
    return parseFloat(rem) * 16;
  };

  // Read rather than duplicated: a copy of 0.9 here would keep passing after
  // somebody changed the real one.
  const proScale = (() => {
    const css = readFileSync("src/index.css", "utf8");
    const found = /\.surface-pro\s*\{[^}]*--type-scale:\s*([\d.]+)/.exec(css)?.[1];
    if (!found) throw new Error("index.css no longer sets --type-scale on .surface-pro");
    return parseFloat(found);
  })();

  it("keeps inputs at or above the 16px iOS zoom floor on both surfaces", () => {
    expect(px("base")).toBeGreaterThanOrEqual(16);
    expect(px("base") * proScale).toBeGreaterThanOrEqual(16);
  });

  it("rises monotonically, so a bigger token is never smaller type", () => {
    const order = ["2xs", "xs", "sm", "md", "base", "lg", "xl", "2xl", "3xl", "4xl"];
    const values = order.map(px);
    expect(values).toEqual([...values].sort((a, b) => a - b));
  });
});
