import { describe, expect, it } from "vitest";
import {
  NON_TEACHING_FALLBACK_LABEL,
  buildPeriodDisplay,
  formatPeriodHeader,
  type PeriodDisplaySource,
} from "./periodDisplay";

function slot(
  weekday: number,
  period: number,
  isTeachingPeriod: boolean,
  label: string | null = null,
): PeriodDisplaySource {
  return { weekday, period, is_teaching_period: isTeachingPeriod, label };
}

// The demo data: 0 早自習, 1-4 teaching, 5 午餐/午休, 6-8 teaching, and
// 9 放學 recorded on Monday only.
function demoSlots(): PeriodDisplaySource[] {
  const slots: PeriodDisplaySource[] = [];
  for (let weekday = 1; weekday <= 5; weekday += 1) {
    slots.push(slot(weekday, 0, false, "早自習"));
    for (const period of [1, 2, 3, 4, 6, 7, 8]) {
      slots.push(slot(weekday, period, true));
    }
    slots.push(slot(weekday, 5, false, "午餐/午休"));
  }
  slots.push(slot(1, 9, false, "放學"));
  return slots;
}

describe("buildPeriodDisplay", () => {
  it("numbers teaching rows 1-7 and names the 早自習 / 午休 / 放學 rows (demo data)", () => {
    const display = buildPeriodDisplay(demoSlots());

    expect(Array.from(display.entries())).toEqual([
      [0, { kind: "nonTeaching", label: "早自習" }],
      [1, { kind: "teaching", number: 1 }],
      [2, { kind: "teaching", number: 2 }],
      [3, { kind: "teaching", number: 3 }],
      [4, { kind: "teaching", number: 4 }],
      [5, { kind: "nonTeaching", label: "午餐/午休" }],
      [6, { kind: "teaching", number: 5 }],
      [7, { kind: "teaching", number: 6 }],
      [8, { kind: "teaching", number: 7 }],
      // Only Monday has a record -- still a non-teaching row.
      [9, { kind: "nonTeaching", label: "放學" }],
    ]);
  });

  it("numbers every row when all periods are teaching", () => {
    const display = buildPeriodDisplay([slot(1, 1, true), slot(1, 2, true), slot(2, 3, true)]);

    expect(Array.from(display.values())).toEqual([
      { kind: "teaching", number: 1 },
      { kind: "teaching", number: 2 },
      { kind: "teaching", number: 3 },
    ]);
  });

  it("treats a period as teaching when ANY weekday teaches in it", () => {
    // Wednesday period 1 is 導師時間, the other days teach.
    const display = buildPeriodDisplay([
      slot(1, 1, true),
      slot(3, 1, false, "導師時間"),
      slot(1, 2, true),
    ]);

    expect(display.get(1)).toEqual({ kind: "teaching", number: 1 });
    expect(display.get(2)).toEqual({ kind: "teaching", number: 2 });
  });

  it("falls back to 非教學時段 when no slot of a non-teaching row has a label", () => {
    const display = buildPeriodDisplay([slot(1, 0, false), slot(2, 0, false, "  "), slot(1, 1, true)]);

    expect(display.get(0)).toEqual({ kind: "nonTeaching", label: NON_TEACHING_FALLBACK_LABEL });
    expect(NON_TEACHING_FALLBACK_LABEL).toBe("非教學時段");
  });

  it("takes the first label by weekday, whatever order the slots come in", () => {
    const display = buildPeriodDisplay([slot(4, 5, false, "午休"), slot(2, 5, false, "午餐")]);

    expect(display.get(5)).toEqual({ kind: "nonTeaching", label: "午餐" });
  });

  it("returns an empty map for no time slots", () => {
    expect(buildPeriodDisplay([]).size).toBe(0);
  });

  it("numbers by ascending period even when the raw numbers have gaps", () => {
    const display = buildPeriodDisplay([
      slot(1, 10, true),
      slot(1, 3, true),
      slot(1, 7, false, "午休"),
      slot(1, 12, true),
    ]);

    expect(Array.from(display.entries())).toEqual([
      [3, { kind: "teaching", number: 1 }],
      [7, { kind: "nonTeaching", label: "午休" }],
      [10, { kind: "teaching", number: 2 }],
      [12, { kind: "teaching", number: 3 }],
    ]);
  });
});

describe("formatPeriodHeader", () => {
  const display = buildPeriodDisplay(demoSlots());

  it("shows the teaching number, not the raw period", () => {
    expect(formatPeriodHeader(1, display)).toBe("第 1 節");
    expect(formatPeriodHeader(6, display)).toBe("第 5 節");
    expect(formatPeriodHeader(8, display)).toBe("第 7 節");
  });

  it("shows only the name of a non-teaching row", () => {
    expect(formatPeriodHeader(0, display)).toBe("早自習");
    expect(formatPeriodHeader(5, display)).toBe("午餐/午休");
    expect(formatPeriodHeader(9, display)).toBe("放學");
  });

  it("falls back to the raw period for a period it doesn't know", () => {
    expect(formatPeriodHeader(42, display)).toBe("第 42 節");
  });
});
