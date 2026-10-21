import { describe, expect, it } from "vitest";
import { buildPeriodDisplay } from "./periodDisplay";
import { summarizeSlots } from "./recordSettings";
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
