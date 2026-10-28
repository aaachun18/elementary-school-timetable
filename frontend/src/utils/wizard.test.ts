import { describe, expect, it } from "vitest";
import {
  canJumpToStep,
  isSemesterStepLocked,
  WIZARD_STEPS,
  buildTimeSlotGrid,
  currentAcademicYear,
  currentSemesterNumber,
  isWizardStep,
  periodsRangeError,
  slotKey,
} from "./wizard";
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
      "combined",
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

describe("currentAcademicYear / currentSemesterNumber", () => {
  it("starts 115 學年度 on 2026-08-01 and ends it on 2027-07-31", () => {
    expect(currentAcademicYear(new Date(2026, 6, 31))).toBe(114);
    expect(currentAcademicYear(new Date(2026, 7, 1))).toBe(115);
    expect(currentAcademicYear(new Date(2026, 9, 20))).toBe(115);
    expect(currentAcademicYear(new Date(2027, 6, 31))).toBe(115);
    expect(currentAcademicYear(new Date(2027, 7, 1))).toBe(116);
  });

  it("is 第 1 學期 from August to January and 第 2 學期 from February to July", () => {
    expect(currentSemesterNumber(new Date(2026, 7, 1))).toBe(1);
    expect(currentSemesterNumber(new Date(2027, 0, 31))).toBe(1);
    expect(currentSemesterNumber(new Date(2027, 1, 1))).toBe(2);
    expect(currentSemesterNumber(new Date(2027, 6, 31))).toBe(2);
  });
});

describe("isSemesterStepLocked", () => {
  it("is open when starting afresh (no record yet)", () => {
    expect(isSemesterStepLocked(null)).toBe(false);
  });

  it("is locked once the record exists", () => {
    expect(isSemesterStepLocked(12)).toBe(true);
  });
});

describe("canJumpToStep", () => {
  it("allows no step before the record exists", () => {
    expect(canJumpToStep(0, 1, false)).toBe(false);
    expect(canJumpToStep(2, 1, false)).toBe(false);
  });

  it("allows every other step once it exists, step 1 included", () => {
    expect(canJumpToStep(0, 1, true)).toBe(true);
    expect(canJumpToStep(3, 1, true)).toBe(true);
  });

  it("never the current step", () => {
    expect(canJumpToStep(1, 1, true)).toBe(false);
  });
});
