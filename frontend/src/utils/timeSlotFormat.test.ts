import { describe, expect, it } from "vitest";
import { buildPeriodDisplay, type PeriodDisplaySource } from "./periodDisplay";
import { formatTimeSlotLabel, formatWeekday } from "./timeSlotFormat";

function slot(
  weekday: number,
  period: number,
  isTeachingPeriod: boolean,
  label: string | null = null,
): PeriodDisplaySource {
  return { weekday, period, is_teaching_period: isTeachingPeriod, label };
}

// Monday in the demo layout: 0 早自習, 1-4, 5 午餐/午休, 6-8, 9 放學. The
// numbering only depends on which periods teach, so one day is enough.
const DISPLAY = buildPeriodDisplay([
  slot(1, 0, false, "早自習"),
  slot(1, 1, true),
  slot(1, 2, true),
  slot(1, 3, true),
  slot(1, 4, true),
  slot(1, 5, false, "午餐/午休"),
  slot(1, 6, true),
  slot(1, 7, true),
  slot(1, 8, true),
  slot(1, 9, false, "放學"),
]);

describe("formatWeekday", () => {
  it("names Monday-Friday and falls back for an unknown code", () => {
    expect(formatWeekday(1)).toBe("星期一");
    expect(formatWeekday(5)).toBe("星期五");
    expect(formatWeekday(7)).toBe("星期代碼 7");
  });
});

describe("formatTimeSlotLabel", () => {
  it("uses the teaching number: raw period 8 on Friday is 第 7 節", () => {
    expect(formatTimeSlotLabel(slot(5, 8, true), DISPLAY)).toBe("星期五第 7 節");
    expect(formatTimeSlotLabel(slot(1, 6, true), DISPLAY)).toBe("星期一第 5 節");
  });

  it("keeps morning numbers unchanged", () => {
    expect(formatTimeSlotLabel(slot(1, 1, true), DISPLAY)).toBe("星期一第 1 節");
    expect(formatTimeSlotLabel(slot(1, 4, true), DISPLAY)).toBe("星期一第 4 節");
  });

  it("names a non-teaching slot instead of numbering it", () => {
    expect(formatTimeSlotLabel(slot(1, 0, false, "早自習"), DISPLAY)).toBe("星期一早自習");
    expect(formatTimeSlotLabel(slot(3, 5, false, "午餐/午休"), DISPLAY)).toBe("星期三午餐/午休");
    expect(formatTimeSlotLabel(slot(1, 9, false, "放學"), DISPLAY)).toBe("星期一放學");
  });

  it("names an unlabelled non-teaching slot by its row, then the generic fallback", () => {
    expect(formatTimeSlotLabel(slot(2, 5, false), DISPLAY)).toBe("星期二午餐/午休");
    // A non-teaching slot inside a teaching row (e.g. one day's 導師時間).
    expect(formatTimeSlotLabel(slot(2, 1, false), DISPLAY)).toBe("星期二非教學時段");
    expect(formatTimeSlotLabel(slot(2, 1, false, "導師時間"), DISPLAY)).toBe("星期二導師時間");
  });

  it("falls back to the raw period when the map doesn't know the period", () => {
    expect(formatTimeSlotLabel(slot(2, 8, true), new Map())).toBe("星期二第 8 節");
  });
});
