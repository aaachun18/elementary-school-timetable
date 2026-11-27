// v3: 檢視排課設定 -- a record's slot settings (a teacher's unavailable
// slots, a grade's open slots) as short readable text. Pure, no React.

import type { PeriodDisplayMap } from "./periodDisplay";
import { formatWeekday } from "./timeSlotFormat";
import type { TimeSlot } from "../types/timeSlot";

// Each weekday's teaching numbers among `timeSlotIds`. Ids of unknown
// slots and non-teaching slots are skipped.
function teachingNumbersByWeekday(
  timeSlotIds: readonly number[],
  timeSlotById: ReadonlyMap<number, TimeSlot>,
  periodDisplay: PeriodDisplayMap,
): Map<number, number[]> {
  const numbersByWeekday = new Map<number, number[]>();
  for (const id of timeSlotIds) {
    const slot = timeSlotById.get(id);
    const display = slot === undefined ? undefined : periodDisplay.get(slot.period);
    if (slot === undefined || display === undefined || display.kind !== "teaching") {
      continue;
    }
    const numbers = numbersByWeekday.get(slot.weekday) ?? [];
    numbers.push(display.number);
    numbersByWeekday.set(slot.weekday, numbers);
  }
  return numbersByWeekday;
}

// 「星期一 第 1–4 節；星期二 第 1、3 節」: per weekday (Monday first), the
// periods by their teaching number, consecutive runs joined with 「–」.
// Ids of unknown slots are skipped; nothing at all -> 「無」.
export function summarizeSlots(
  timeSlotIds: readonly number[],
  timeSlotById: ReadonlyMap<number, TimeSlot>,
  periodDisplay: PeriodDisplayMap,
): string {
  const numbersByWeekday = teachingNumbersByWeekday(timeSlotIds, timeSlotById, periodDisplay);
  if (numbersByWeekday.size === 0) {
    return "無";
  }
  return [...numbersByWeekday.entries()]
    .sort(([a], [b]) => a - b)
    .map(([weekday, numbers]) => `${formatWeekday(weekday)} 第 ${joinRuns(numbers)} 節`)
    .join("；");
}

// Task 98 Phase D: one row of the compact 年級可排節次 table -- for each of
// `weekdays`, its open teaching periods (「1–4」, 「1–2、4」), or 「—」.
export function slotCellsByWeekday(
  timeSlotIds: readonly number[],
  timeSlotById: ReadonlyMap<number, TimeSlot>,
  periodDisplay: PeriodDisplayMap,
  weekdays: readonly number[],
): string[] {
  const numbersByWeekday = teachingNumbersByWeekday(timeSlotIds, timeSlotById, periodDisplay);
  return weekdays.map((weekday) => {
    const numbers = numbersByWeekday.get(weekday);
    return numbers === undefined ? "—" : joinRuns(numbers);
  });
}

// [1, 2, 3, 4, 6] -> 「1–4、6」.
function joinRuns(numbers: readonly number[]): string {
  const sorted = [...new Set(numbers)].sort((a, b) => a - b);
  const runs: string[] = [];
  let start = sorted[0];
  let previous = sorted[0];
  for (const number of [...sorted.slice(1), Number.NaN]) {
    if (number === previous + 1) {
      previous = number;
      continue;
    }
    runs.push(start === previous ? String(start) : `${start}–${previous}`);
    start = number;
    previous = number;
  }
  return runs.join("、");
}

// One page of a list, 1-based. A page past either end is clamped to the
// first / last one, so the result always has a real page (an empty list
// still has page 1 of 1).
export function paginate<T>(
  items: readonly T[],
  page: number,
  pageSize: number,
): { items: T[]; page: number; pageCount: number } {
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const current = Math.min(Math.max(1, page), pageCount);
  const start = (current - 1) * pageSize;
  return { items: items.slice(start, start + pageSize), page: current, pageCount };
}
