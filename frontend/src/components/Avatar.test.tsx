import { describe, expect, it } from "vitest";
import { initials } from "./Avatar";

describe("the initials on the account chip", () => {
  it("takes the first and last word of a display name", () => {
    expect(initials("Oscar Arroyo Vega", "x@y.com")).toBe("OV");
  });

  it("takes the first two characters of a single word, never a guessed surname", () => {
    expect(initials("Cher", "x@y.com")).toBe("CH");
  });

  it("falls back to the email, splitting the local part on its separators", () => {
    expect(initials(null, "oscar.arroyo@gmail.com")).toBe("OA");
    expect(initials(null, "arroscar@gmail.com")).toBe("AR");
    expect(initials("   ", "ana-beck@x.com")).toBe("AB");
  });

  it("gives one letter only when there is no second one", () => {
    expect(initials("X", null)).toBe("X");
  });

  it("never puts punctuation in the chip", () => {
    // The second character of a single word is taken raw, so a stage name or
    // an Irish surname would otherwise read "T-" and "O'".
    expect(initials("O'Brien", null)).toBe("OB");
    expect(initials("T-Pain", null)).toBe("TP");
    expect(initials("Jean-Pierre", null)).toBe("JP");
    expect(initials("D’Angelo", null)).toBe("DA");
    expect(initials(null, "o'brien@x.com")).toBe("OB");
  });

  it("keeps accents and non-latin scripts whole", () => {
    expect(initials("Ángela Ruiz", null)).toBe("ÁR");
    expect(initials("Ольга Иванова", null)).toBe("ОИ");
  });

  it("does not cut an astral character in half", () => {
    // Indexing with [0] returns half a surrogate pair, which renders as the
    // replacement box rather than the character.
    expect(initials("🎸 Strings", null)).toBe("🎸S");
    expect([...initials("🎸 Strings", null)]).toHaveLength(2);
  });

  it("upper-cases through the reader's locale", () => {
    expect(initials("ana", null)).toBe("AN");
    // toLocaleUpperCase follows the host locale, so a browser set to Turkish
    // gets "İ" here and an English one gets "I". Asserting either would be
    // asserting the test runner's locale, so this only pins the casing itself.
    expect(initials("işık", null)).toHaveLength(2);
  });

  it("returns nothing when there is nothing to work with", () => {
    // The caller renders the old account icon for this — it is the signed-out
    // shape, and a blank circle would read as a broken image.
    expect(initials(null, null)).toBe("");
    expect(initials("", "")).toBe("");
    expect(initials(undefined, undefined)).toBe("");
  });
});
