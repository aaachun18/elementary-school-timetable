import { describe, expect, it } from "vitest";
import {
  WIZARD_STEPS,
  buildTimeSlotGrid,
  isWizardStep,
  nextVersionNumber,
  periodsRangeError,
  slotKey,
} from "./wizard";
import type { ScheduleVersion } from "../types/scheduleVersion";
import type { TimeSlot } from "../types/timeSlot";

describe("isWizardStep", () => {
  it("accepts the step keys only", () => {
    expect(isWizardStep("teachers")).toBe(true);
    expect(isWizardStep("run")).toBe(true);
    expect(isWizardStep("nope")).toBe(false);
    expect(isWizardStep(null)).toBe(false);
  });

  it("has no 班級 step: classes are kept on 學校資料", () => {
    expect(isWizardStep("classes")).toBe(false);
    expect(WIZARD_STEPS.map((step) => step.key)).toEqual([
      "semester",
      "teachers",
      "grades",
      "requirements",
      "run",
    ]);
  });
});

describe("buildTimeSlotGrid", () => {
  it("lays the school's slots out by weekday and period", () => {
    const slot = (id: number, weekday: number, period: number) =>
      ({ id, weekday, period, is_teaching_period: true }) as TimeSlot;
    const grid = buildTimeSlotGrid([slot(1, 2, 3), slot(2, 1, 0), slot(3, 1, 3)]);

    expect(grid.weekdays).toEqual([1, 2]);
    expect(grid.periods).toEqual([0, 3]);
    expect(grid.slotAt.get(slotKey(2, 3))?.id).toBe(1);
    expect(grid.slotAt.get(slotKey(2, 0))).toBeUndefined();
  });
});

describe("nextVersionNumber", () => {
  it("is one past the semester's highest, 1 for a new semester", () => {
    const versions = [
      { semester_id: 1, version_number: 1 },
      { semester_id: 1, version_number: 3 },
      { semester_id: 2, version_number: 9 },
    ] as ScheduleVersion[];

    expect(nextVersionNumber(versions, 1)).toBe(4);
    expect(nextVersionNumber(versions, 5)).toBe(1);
  });
});

describe("periodsRangeError", () => {
  it("accepts a valid range, zero included", () => {
    expect(periodsRangeError("0", "0")).toBeNull();
    expect(periodsRangeError("2", "18")).toBeNull();
  });

  it("refuses blanks, fractions, negatives and min above max", () => {
    expect(periodsRangeError("", "5")).toBe("請輸入整數節數");
    expect(periodsRangeError("1.5", "5")).toBe("請輸入整數節數");
    expect(periodsRangeError("-1", "5")).toBe("節數不得為負數");
    expect(periodsRangeError("6", "5")).toBe("最低每週節數不得大於最高每週節數");
  });
});
