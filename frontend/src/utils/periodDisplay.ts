// Task 78 / v3: what a period number is CALLED on screen. A school's
// periods are a fixed 0-9 (國小) or 0-10 (國中/高中) grid in the database,
// but people count only the periods that teach: 0 is 早自習, 5 午休 and the
// last one 放學, so 國小's afternoon periods 6-8 are 「第 5-7 節」 and
// 國中 / 高中 have 第 1-8 節.
//
// Rules (per period, across all weekdays):
// - a teaching row: ANY weekday has an is_teaching_period=true slot at this
//   period. Numbered 1, 2, 3 ... in period order, counting teaching rows
//   only -- shown as "第 {number} 節".
// - a non-teaching row: every other period that has at least one slot. It
//   has no number, only a name: the first non-null label (by weekday), or
//   NON_TEACHING_FALLBACK_LABEL.

import type { TimeSlot } from "../types/timeSlot";

export const NON_TEACHING_FALLBACK_LABEL = "非教學時段";

export type PeriodDisplay =
  | { kind: "teaching"; number: number }
  | { kind: "nonTeaching"; label: string };

export type PeriodDisplayMap = ReadonlyMap<number, PeriodDisplay>;

export type PeriodDisplaySource = Pick<
  TimeSlot,
  "weekday" | "period" | "is_teaching_period" | "label"
>;

export function buildPeriodDisplay(
  timeSlots: Iterable<PeriodDisplaySource>,
): PeriodDisplayMap {
  const slotsByPeriod = new Map<number, PeriodDisplaySource[]>();
  for (const timeSlot of timeSlots) {
    const slots = slotsByPeriod.get(timeSlot.period);
    if (slots === undefined) {
      slotsByPeriod.set(timeSlot.period, [timeSlot]);
    } else {
      slots.push(timeSlot);
    }
  }

  const display = new Map<number, PeriodDisplay>();
  const periods = Array.from(slotsByPeriod.keys()).sort((a, b) => a - b);
  let teachingNumber = 0;
  for (const period of periods) {
    const slots = slotsByPeriod.get(period) ?? [];
    if (slots.some((timeSlot) => timeSlot.is_teaching_period)) {
      teachingNumber += 1;
      display.set(period, { kind: "teaching", number: teachingNumber });
      continue;
    }
    const labelled = [...slots]
      .sort((a, b) => a.weekday - b.weekday)
      .find((timeSlot) => timeSlot.label !== null && timeSlot.label.trim() !== "");
    display.set(period, {
      kind: "nonTeaching",
      label: labelled?.label ?? NON_TEACHING_FALLBACK_LABEL,
    });
  }
  return display;
}

// The timetable's row header: "第 N 節" for a teaching row, the row's name
// for a non-teaching one. A period missing from the map (should not happen:
// the grid's rows come from the same time slots) falls back to the raw
// number so nothing renders blank.
export function formatPeriodHeader(period: number, periodDisplay: PeriodDisplayMap): string {
  const display = periodDisplay.get(period);
  if (display === undefined) {
    return `第 ${period} 節`;
  }
  return display.kind === "teaching" ? `第 ${display.number} 節` : display.label;
}
