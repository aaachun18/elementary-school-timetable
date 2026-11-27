// 開始排課's step navigation. Task 103: every step up to the furthest one the
// record has reached can be clicked -- the later ones too, after going back
// (no step is checked again on the way: step 6's 排課前檢查 is what guards
// 自動排課); a step beyond it can't, so moving on to a new step is only ever
// the step's own 下一步 / 儲存並下一步. The furthest step only goes up, and
// is kept on the record (ScheduleVersion.wizard_furthest_step), so it holds
// after a refresh. Once the record is scheduled the whole row is read only.
// A URL (or the browser's back / forward) naming a later step than the
// furthest one lands on that furthest step instead. Pure, no React
// (wizardNav.test.ts).

export type NavItemState =
  // Reached before (earlier or later than the current step): clickable.
  | "reachable"
  | "current"
  // Never reached: gray, aria-disabled, not focusable.
  | "locked"
  // The record is scheduled: nothing is clickable.
  | "readonly";

export const LOCKED_STEP_HINT = "請依序完成前面的步驟";

// `furthestIndex` null (not known yet): the current step is the furthest.
export function navItemState(
  index: number,
  currentIndex: number,
  furthestIndex: number | null,
  isReadOnly: boolean,
): NavItemState {
  if (index === currentIndex) {
    return "current";
  }
  if (isReadOnly) {
    return "readonly";
  }
  return index <= furthestAfter(furthestIndex, currentIndex) ? "reachable" : "locked";
}

// The step an entry (resuming, a link, an edited URL, a refresh) may open:
// the one asked for, unless that is later than the furthest step reached
// -- then the furthest one. Nothing known about the record yet (null): the
// entry itself is all there is to go by.
export function allowedEntryIndex(requestedIndex: number, furthestIndex: number | null): number {
  return furthestIndex === null ? requestedIndex : Math.min(requestedIndex, furthestIndex);
}

// The furthest step after arriving at `index`: only ever goes up. A record
// that has none yet (made before Task 103) starts from the step it opens.
export function furthestAfter(previous: number | null, index: number): number {
  return previous === null ? index : Math.max(previous, index);
}

// Whether the furthest step just reached is worth saving on the record:
// only a step beyond the stored one (the backend keeps the higher anyway).
export function isNewFurthest(stored: number | null, reached: number): boolean {
  return stored === null || reached > stored;
}

// Leaving a step through the navigation: ask first when it has unsaved
// changes (only 教師設定 keeps any; every other step saves as it goes).
export const LEAVE_STEP_CONFIRM = {
  title: "離開這一步？",
  message: "這一步有尚未儲存的變更，離開後會遺失。",
  confirmLabel: "不儲存並返回",
} as const;
