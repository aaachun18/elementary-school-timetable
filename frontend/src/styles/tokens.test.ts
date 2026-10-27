/// <reference types="node" />
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { contrastRatio, MIN_TEXT_CONTRAST, parseThemeColors } from "../utils/contrast";

// Task 98: the colors are read from index.css's @theme block -- the one
// place they are written -- so this test can never drift from what the
// browser actually shows. Only token NAMES are listed here.
const css = readFileSync(new URL("../index.css", import.meta.url), "utf8");
const colors = parseThemeColors(css);

// [text token, background token] -- every pair the design system puts text on.
const TEXT_PAIRS: ReadonlyArray<readonly [string, string]> = [
  // Solid buttons: white text.
  ["on-accent", "primary"],
  ["on-accent", "primary-hover"],
  ["on-accent", "success"],
  ["on-accent", "success-hover"],
  ["on-accent", "danger"],
  ["on-accent", "danger-hover"],
  // Secondary button.
  ["on-secondary", "secondary"],
  ["on-secondary", "secondary-hover"],
  // Ghost button / text link / active tab.
  ["primary", "surface"],
  ["primary", "page"],
  ["primary", "primary-soft"],
  ["primary-hover", "primary-soft"],
  // Neutral icons and secondary text.
  ["icon", "surface"],
  ["icon", "page"],
  ["icon-hover", "surface"],
  ["icon-hover", "secondary"],
  ["text-muted", "surface"],
  ["text-muted", "page"],
  // Status badges.
  ["badge-info-fg", "badge-info-bg"],
  ["badge-manual-fg", "badge-manual-bg"],
  ["badge-warning-fg", "badge-warning-bg"],
  ["badge-success-fg", "badge-success-bg"],
  ["badge-neutral-fg", "badge-neutral-bg"],
];

function tokenColor(name: string): string {
  const value = colors.get(name);
  if (value === undefined) {
    throw new Error(`index.css 的 @theme 沒有定義 --color-${name}`);
  }
  return value;
}

describe("design tokens (index.css @theme)", () => {
  it.each(TEXT_PAIRS)("%s on %s reaches a 4.5 contrast", (text, background) => {
    expect(contrastRatio(tokenColor(text), tokenColor(background))).toBeGreaterThanOrEqual(MIN_TEXT_CONTRAST);
  });

  it("keeps the agreed values for the main colors", () => {
    expect(tokenColor("primary")).toBe("#00749b");
    expect(tokenColor("success")).toBe("#2e7d32");
    expect(tokenColor("danger")).toBe("#d32f2f");
  });
});

describe("contrastRatio", () => {
  it("is 21 for black on white and 1 for a color on itself", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(contrastRatio("#00749b", "#00749b")).toBeCloseTo(1, 5);
  });

  it("matches the values the palette was chosen with", () => {
    expect(contrastRatio("#ffffff", "#00749b")).toBeCloseTo(5.29, 1);
    expect(contrastRatio("#ffffff", "#d32f2f")).toBeCloseTo(4.98, 1);
    expect(contrastRatio("#1f2937", "#e7e7e7")).toBeCloseTo(11.87, 1);
  });

  it("fails a pair below 4.5 (the old amber-on-white idea)", () => {
    expect(contrastRatio("#f59e0b", "#ffffff")).toBeLessThan(MIN_TEXT_CONTRAST);
  });

  it("accepts the short #rgb form and rejects anything else", () => {
    expect(contrastRatio("#fff", "#000")).toBeCloseTo(21, 5);
    expect(() => contrastRatio("white", "#000")).toThrow();
  });
});

describe("parseThemeColors", () => {
  it("reads only the @theme block", () => {
    const parsed = parseThemeColors("body { --color-x: #111111; }\n@theme {\n  --color-a: #ABCDEF;\n}\n");
    expect(parsed.get("a")).toBe("#abcdef");
    expect(parsed.has("x")).toBe(false);
  });
});
