// weekday is 1-5 (Monday-Friday) per backend/app/models/time_slot.py's
// CheckConstraint. Shared by DataBrowser.tsx's 時段 tab and the per-teacher
// unavailable-slots detail, both of which need a human-readable label
// instead of the raw weekday/period integers.
import {
  NON_TEACHING_FALLBACK_LABEL,
  type PeriodDisplayMap,
  type PeriodDisplaySource,
} from "./periodDisplay";

const WEEKDAY_LABELS: Record<number, string> = {
  1: "星期一",
  2: "星期二",
  3: "星期三",
  4: "星期四",
  5: "星期五",
};

export function formatWeekday(weekday: number): string {
  return WEEKDAY_LABELS[weekday] ?? `星期代碼 ${weekday}`;
}

// Task 78: periods are shown by their TEACHING number (utils/periodDisplay.ts),
// e.g. raw period 8 on a day with 早自習 and 午休 is "星期五第 7 節"; a
// non-teaching slot shows its name instead ("星期一早自習"). periodDisplay
// must be built from ALL time slots, not just the ones being labelled.
// A period missing from the map falls back to the raw number.
export function formatTimeSlotLabel(
  timeSlot: PeriodDisplaySource,
  periodDisplay: PeriodDisplayMap,
): string {
  const weekday = formatWeekday(timeSlot.weekday);
  const display = periodDisplay.get(timeSlot.period);
  // A non-teaching slot is named by its own label first: one period can be
  // 早自習 on Monday and 導師時間 on Wednesday.
  if (!timeSlot.is_teaching_period) {
    const rowLabel = display?.kind === "nonTeaching" ? display.label : null;
    return `${weekday}${timeSlot.label ?? rowLabel ?? NON_TEACHING_FALLBACK_LABEL}`;
  }
  if (display === undefined) {
    return `${weekday}第 ${timeSlot.period} 節`;
  }
  return display.kind === "teaching"
    ? `${weekday}第 ${display.number} 節`
    : `${weekday}${display.label}`;
}
