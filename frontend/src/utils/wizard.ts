// Task 98: the scheduling wizard's (pages/SchedulingWizard.tsx) pure rules
// -- its steps, grade names, class name suggestions, the time slot grid
// the pickers draw, and the next version number. No React, no requests.

import type { ScheduleVersion } from "../types/scheduleVersion";
import type { TimeSlot } from "../types/timeSlot";

// --- Steps ---

export type WizardStepKey =
  | "semester"
  | "teachers"
  | "grades"
  | "classes"
  | "requirements"
  | "run";

export const WIZARD_STEPS: readonly { key: WizardStepKey; label: string }[] = [
  { key: "semester", label: "學年度與學期" },
  { key: "teachers", label: "教師設定" },
  { key: "grades", label: "年級與可排節次" },
  { key: "classes", label: "班級" },
  { key: "requirements", label: "科目需求" },
  { key: "run", label: "確認並排課" },
];

export function isWizardStep(value: string | null): value is WizardStepKey {
  return value !== null && WIZARD_STEPS.some((step) => step.key === value);
}

// --- Grades ---

export type SchoolStage = "elementary" | "juniorHigh";

export const SCHOOL_STAGE_LABELS: Record<SchoolStage, string> = {
  elementary: "國小（一到六年級）",
  juniorHigh: "國中（七到九年級）",
};

export const STAGE_LEVELS: Record<SchoolStage, readonly number[]> = {
  elementary: [1, 2, 3, 4, 5, 6],
  juniorHigh: [7, 8, 9],
};

const CHINESE_NUMBERS = ["一", "二", "三", "四", "五", "六", "七", "八", "九"];

// 1 -> 「一年級」 ... 9 -> 「九年級」.
export function gradeName(level: number): string {
  return `${CHINESE_NUMBERS[level - 1] ?? level}年級`;
}

// The stage a set of levels belongs to: 國中 once any level is 7-9.
export function stageOfLevels(levels: readonly number[]): SchoolStage {
  return levels.some((level) => level >= 7) ? "juniorHigh" : "elementary";
}

// --- Classes ---

const CLASS_NUMBERS = Array.from({ length: 12 }, (_, index) => String(index + 1));
const HEAVENLY_STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"];
const VIRTUES = ["忠", "孝", "仁", "愛", "信", "義", "和", "平"];

// The class name suggestions for a grade: 「一年1班」, 「一年甲班」,
// 「一年忠班」 ... -- typing 「甲」 or 「忠」 filters to them. Free text is
// allowed too; these are only suggestions.
export function classNameSuggestions(level: number): string[] {
  const prefix = `${CHINESE_NUMBERS[level - 1] ?? level}年`;
  return [...CLASS_NUMBERS, ...HEAVENLY_STEMS, ...VIRTUES].map((token) => `${prefix}${token}班`);
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

// --- Versions ---

// A new run's version number: one past the semester's highest.
export function nextVersionNumber(versions: readonly ScheduleVersion[], semesterId: number): number {
  return (
    versions
      .filter((version) => version.semester_id === semesterId)
      .reduce((max, version) => Math.max(max, version.version_number), 0) + 1
  );
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
