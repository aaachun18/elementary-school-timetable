import { describe, expect, it } from "vitest";
import { buildPeriodDisplay } from "./periodDisplay";
import { paginate, slotCellsByWeekday, summarizeSlots } from "./recordSettings";
import type { TimeSlot } from "../types/timeSlot";

function slot(id: number, weekday: number, period: number, teaching = true): TimeSlot {
  return {
    id,
    weekday,
    period,
    is_teaching_period: teaching,
    label: teaching ? null : period === 0 ? "早自習" : "午休",
  } as TimeSlot;
}

// Monday and Tuesday: 0 早自習, 1-4, 5 午休, 6-8 (shown as 第 5-7 節).
const SLOTS = [1, 2].flatMap((weekday) =>
  [0, 1, 2, 3, 4, 5, 6, 7, 8].map((period) =>
    slot(weekday * 10 + period, weekday, period, period !== 0 && period !== 5),
  ),
);
const BY_ID = new Map(SLOTS.map((item) => [item.id, item]));
const DISPLAY = buildPeriodDisplay(SLOTS);

describe("summarizeSlots", () => {
  it("lists each weekday's periods by teaching number, runs joined", () => {
    expect(summarizeSlots([11, 12, 13, 14, 16, 17, 18], BY_ID, DISPLAY)).toBe("星期一 第 1–7 節");
    expect(summarizeSlots([21, 23, 11, 12], BY_ID, DISPLAY)).toBe("星期一 第 1–2 節；星期二 第 1、3 節");
  });

  it("skips unknown and non-teaching slots, and says 無 for nothing", () => {
    expect(summarizeSlots([999, 10, 15], BY_ID, DISPLAY)).toBe("無");
    expect(summarizeSlots([], BY_ID, DISPLAY)).toBe("無");
  });
});

describe("slotCellsByWeekday", () => {
  it("gives each weekday its open periods, runs joined", () => {
    expect(slotCellsByWeekday([11, 12, 13, 14, 21, 22, 24], BY_ID, DISPLAY, [1, 2])).toEqual(["1–4", "1–2、4"]);
  });

  it("shows 「—」 for a weekday with nothing open (or only non-teaching slots)", () => {
    expect(slotCellsByWeekday([10, 15, 21], BY_ID, DISPLAY, [1, 2, 3])).toEqual(["—", "1", "—"]);
  });
});

describe("paginate", () => {
  const items = Array.from({ length: 23 }, (_, index) => index + 1);

  it("cuts the list into pages of the given size", () => {
    expect(paginate(items, 1, 10)).toEqual({ items: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], page: 1, pageCount: 3 });
    expect(paginate(items, 3, 10)).toEqual({ items: [21, 22, 23], page: 3, pageCount: 3 });
  });

  it("clamps a page past either end", () => {
    expect(paginate(items, 9, 10).page).toBe(3);
    expect(paginate(items, 0, 10).page).toBe(1);
  });

  it("has one empty page for an empty list", () => {
    expect(paginate([], 1, 10)).toEqual({ items: [], page: 1, pageCount: 1 });
  });
});
