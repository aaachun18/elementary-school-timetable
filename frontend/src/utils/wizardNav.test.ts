import { describe, expect, it } from "vitest";
import { allowedEntryIndex, furthestAfter, isNewFurthest, navItemState, type NavItemState } from "./wizardNav";

const STEP_COUNT = 6;

function row(currentIndex: number, furthestIndex: number | null, isReadOnly = false): NavItemState[] {
  return Array.from({ length: STEP_COUNT }, (_, index) =>
    navItemState(index, currentIndex, furthestIndex, isReadOnly),
  );
}

describe("navItemState", () => {
  it("locks every later step on a new record (step 1)", () => {
    expect(row(0, 0)).toEqual(["current", "locked", "locked", "locked", "locked", "locked"]);
  });

  it("opens the steps up to the furthest one reached (step 4)", () => {
    expect(row(3, 3)).toEqual(["reachable", "reachable", "reachable", "current", "locked", "locked"]);
  });

  it("keeps the later reached steps open after going back (step 4 -> 2)", () => {
    // Task 103 (replaces Task 102's "back only"): going back no longer
    // locks steps 3-4 again.
    expect(row(1, 3)).toEqual(["reachable", "current", "reachable", "reachable", "locked", "locked"]);
  });

  it("takes the current step as the furthest when none is known yet", () => {
    expect(row(2, null)).toEqual(["reachable", "reachable", "current", "locked", "locked", "locked"]);
  });

  it("is read only once the record is scheduled", () => {
    expect(row(5, 5, true)).toEqual(["readonly", "readonly", "readonly", "readonly", "readonly", "current"]);
  });
});

describe("allowedEntryIndex", () => {
  it("sends an edited URL beyond the furthest step back to it (4 -> 6)", () => {
    expect(allowedEntryIndex(5, 3)).toBe(3);
  });

  it("keeps an earlier or the furthest step (a refresh, a link back)", () => {
    expect(allowedEntryIndex(3, 3)).toBe(3);
    expect(allowedEntryIndex(1, 3)).toBe(1);
  });

  it("goes by the entry itself when nothing is known about the record", () => {
    expect(allowedEntryIndex(4, null)).toBe(4);
  });
});

describe("furthestAfter", () => {
  it("moves on, never back (walking forward, then going back and on again)", () => {
    expect(furthestAfter(null, 1)).toBe(1);
    expect(furthestAfter(1, 3)).toBe(3);
    expect(furthestAfter(3, 1)).toBe(3);
    expect(furthestAfter(3, 2)).toBe(3);
  });
});

describe("isNewFurthest", () => {
  it("saves only a step beyond the stored one", () => {
    expect(isNewFurthest(null, 1)).toBe(true);
    expect(isNewFurthest(2, 3)).toBe(true);
    expect(isNewFurthest(3, 3)).toBe(false);
    expect(isNewFurthest(3, 1)).toBe(false);
  });
});
