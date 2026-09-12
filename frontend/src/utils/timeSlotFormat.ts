// weekday is 1-5 (Monday-Friday) per backend/app/models/time_slot.py's
// CheckConstraint. Shared by DataBrowser.tsx's 時段 tab and the per-teacher
// unavailable-slots detail, both of which need a human-readable label
// instead of the raw weekday/period integers.
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

export function formatTimeSlotLabel(timeSlot: {
  weekday: number;
  period: number;
}): string {
  return `${formatWeekday(timeSlot.weekday)}第 ${timeSlot.period} 節`;
}
