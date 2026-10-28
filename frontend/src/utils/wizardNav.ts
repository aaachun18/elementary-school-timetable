// 開始排課's step navigation only goes back: the steps before the current
// one can be clicked, the current one and every later one can't -- moving
// on is only ever the step's own 下一步 / 儲存並下一步. Once the record is
// scheduled the whole row is read only. A URL (or the browser's back /
// forward) naming a later step than the furthest one reached lands on
// that furthest step instead. Pure, no React (wizardNav.test.ts).

export type NavItemState =
  // Before the current step: clickable (check mark, pointer, focus ring).
  | "back"
  | "current"
  // After the current step: gray, aria-disabled, not focusable.
  | "locked"
  // The record is scheduled: nothing is clickable.
  | "readonly";

export const LOCKED_STEP_HINT = "請依序完成前面的步驟";

export function navItemState(index: number, currentIndex: number, isReadOnly: boolean): NavItemState {
  if (index === currentIndex) {
    return "current";
  }
  if (isReadOnly) {
    return "readonly";
  }
  return index < currentIndex ? "back" : "locked";
}

// The step an entry (resuming, a link, an edited URL, a refresh) may open:
// the one asked for, unless that is later than the furthest step reached
// -- then the furthest one. Nothing known about the record yet (null): the
// entry itself is all there is to go by.
export function allowedEntryIndex(requestedIndex: number, furthestIndex: number | null): number {
  return furthestIndex === null ? requestedIndex : Math.min(requestedIndex, furthestIndex);
}

// The furthest step after arriving at `index`.
export function furthestAfter(previous: number | null, index: number): number {
  return previous === null ? index : Math.max(previous, index);
}

// Leaving a step through the navigation: ask first when it has unsaved
// changes (only 教師設定 keeps any; every other step saves as it goes).
export const LEAVE_STEP_CONFIRM = {
  title: "離開這一步？",
  message: "這一步有尚未儲存的變更，離開後會遺失。",
  confirmLabel: "不儲存並返回",
} as const;
