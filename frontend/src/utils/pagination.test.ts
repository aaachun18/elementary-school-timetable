import { describe, expect, it } from "vitest";
import { PAGE_SIZE, clampPage, pageCount, pageLabel, pageSlice, showsPagination } from "./pagination";

const items = Array.from({ length: 23 }, (_, index) => index + 1);

describe("pageCount", () => {
  it("is ten rows to a page, and never less than one page", () => {
    expect(PAGE_SIZE).toBe(10);
    expect(pageCount(23)).toBe(3);
    expect(pageCount(20)).toBe(2);
    expect(pageCount(0)).toBe(1);
  });
});

describe("clampPage", () => {
  it("keeps a page that exists", () => {
    expect(clampPage(2, 23)).toBe(2);
  });

  it("falls back to the last page once that page is empty", () => {
    // Page 3 held row 21 only; deleting it leaves 20 rows (two pages).
    expect(clampPage(3, 20)).toBe(2);
    expect(clampPage(5, 0)).toBe(1);
  });

  it("never goes below page 1", () => {
    expect(clampPage(0, 23)).toBe(1);
    expect(clampPage(-2, 23)).toBe(1);
    expect(clampPage(Number.NaN, 23)).toBe(1);
  });
});

describe("pageSlice", () => {
  it("returns that page's rows", () => {
    expect(pageSlice(items, 1)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    expect(pageSlice(items, 3)).toEqual([21, 22, 23]);
  });

  it("uses the clamped page", () => {
    expect(pageSlice(items, 9)).toEqual([21, 22, 23]);
    expect(pageSlice([], 2)).toEqual([]);
  });
});

describe("showsPagination", () => {
  it("hides the controls for ten rows or fewer", () => {
    expect(showsPagination(10)).toBe(false);
    expect(showsPagination(11)).toBe(true);
  });
});

describe("pageLabel", () => {
  it("says which page of how many", () => {
    expect(pageLabel(2, 23)).toBe("第 2 / 3 頁");
    expect(pageLabel(7, 23)).toBe("第 3 / 3 頁");
  });
});
