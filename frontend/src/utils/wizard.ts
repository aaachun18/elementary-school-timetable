// Task 98: the scheduling wizard's (pages/SchedulingWizard.tsx) pure rules
// -- its steps, the time slot grid the pickers draw, today's academic year
// and the teachers' weekly periods. No React, no requests. (Grade and class
// names: utils/schoolStructure.ts.)

import type { TimeSlot } from "../types/timeSlot";

// --- Steps ---

export type WizardStepKey =
  | "semester"
  | "teachers"
  | "grades"
  | "requirements"
  | "combined"
  | "run";

export const WIZARD_STEPS: readonly { key: WizardStepKey; label: string }[] = [
  { key: "semester", label: "學年度與學期" },
  { key: "teachers", label: "教師設定" },
  { key: "grades", label: "年級與可排節次" },
  { key: "requirements", label: "科目需求" },
  { key: "combined", label: "共同排課" },
  { key: "run", label: "確認並排課" },
];

export function isWizardStep(value: string | null): value is WizardStepKey {
  return value !== null && WIZARD_STEPS.some((step) => step.key === value);
}

// --- The time slot grid the pickers draw ---

export interface TimeSlotGrid {
  weekdays: number[];
  periods: number[];
  // `${weekday}-${period}` -> the slot there, if any.
  slotAt: ReadonlyMap<string, TimeSlot>;
}

export function slotKey(weekday: number, period: number): string {
  return `${weekday}-${period}`;
}

export function buildTimeSlotGrid(timeSlots: readonly TimeSlot[]): TimeSlotGrid {
  const weekdays = [...new Set(timeSlots.map((slot) => slot.weekday))].sort((a, b) => a - b);
  const periods = [...new Set(timeSlots.map((slot) => slot.period))].sort((a, b) => a - b);
  return {
    weekdays,
    periods,
    slotAt: new Map(timeSlots.map((slot) => [slotKey(slot.weekday, slot.period), slot])),
  };
}

// --- Today's academic year and semester (step 1's defaults) ---

// 民國 year = western year - 1911. An academic year runs 8/1 - 7/31: 115
// 學年度 is 2026-08-01 to 2027-07-31. Its 第 1 學期 is August - January,
// 第 2 學期 February - July.
const ROC_YEAR_OFFSET = 1911;
const ACADEMIC_YEAR_START_MONTH = 8; // August
const SECOND_SEMESTER_START_MONTH = 2; // February

export function currentAcademicYear(today: Date): number {
  const month = today.getMonth() + 1;
  const rocYear = today.getFullYear() - ROC_YEAR_OFFSET;
  return month >= ACADEMIC_YEAR_START_MONTH ? rocYear : rocYear - 1;
}

export function currentSemesterNumber(today: Date): number {
  const month = today.getMonth() + 1;
  return month >= SECOND_SEMESTER_START_MONTH && month < ACADEMIC_YEAR_START_MONTH ? 2 : 1;
}

// --- Weekly periods ---

export const WEEKLY_PERIOD_OPTIONS = [1, 2, 3, 4, 5, 6] as const;

// --- Teachers' weekly periods (step 5) ---

// A new teacher's maximum before anyone changes it.
export const DEFAULT_MAX_WEEKLY_PERIODS = 20;

// The same rules the backend enforces (app/services/teacher_periods.py),
// as the form's message -- or null when the range is fine.
export function periodsRangeError(minText: string, maxText: string): string | null {
  const minimum = Number(minText);
  const maximum = Number(maxText);
  if (minText.trim() === "" || maxText.trim() === "" || !Number.isInteger(minimum) || !Number.isInteger(maximum)) {
    return "請輸入整數節數";
  }
  if (minimum < 0 || maximum < 0) {
    return "節數不得為負數";
  }
  if (minimum > maximum) {
    return "最低每週節數不得大於最高每週節數";
  }
  return null;
}
