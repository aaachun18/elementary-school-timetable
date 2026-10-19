// Task 96: what the timetable page refreshes after any adjustment is saved
// (move, swap, 換教師, placing an unscheduled lesson, changing a room) --
// decided in one place, so the five success paths can't drift apart.
// Pure functions, no React (adjustmentRefresh.test.ts).

import { violationIdentityKey } from "./violationMerge";
import type { ConstraintViolationDetail } from "../types/scheduler";

export interface AdjustmentRefreshPlan {
  // The grid (its rooms, teachers, slots).
  reloadTimetable: boolean;
  // The 「未排入課程」 panel (only shown in edit mode).
  reloadUnscheduled: boolean;
  // Run 檢查衝突 again, exactly like pressing 「重新檢查」: only when a
  // result (or its error) is on screen -- a check nobody asked for is
  // never started, so nothing new appears and nothing shifts.
  rerunCheck: boolean;
}

const NOTHING: AdjustmentRefreshPlan = { reloadTimetable: false, reloadUnscheduled: false, rerunCheck: false };

// Adjustments only exist for an ADMIN on a DRAFT; anything else refreshes
// nothing.
export function planAdjustmentRefresh(state: {
  isAdmin: boolean;
  versionStatus: string | null;
  isEditModeOn: boolean;
  isCheckShown: boolean;
}): AdjustmentRefreshPlan {
  if (!state.isAdmin || state.versionStatus !== "DRAFT") {
    return NOTHING;
  }
  return { reloadTimetable: true, reloadUnscheduled: state.isEditModeOn, rerunCheck: state.isCheckShown };
}

// The 「在課表中查看」 cell (amber) points at one problem; once a newer
// check no longer has that problem, the cell is no longer marked. Unknown
// (nothing located, or no check result yet): keep it.
export function isLocatedProblemGone(
  locatedKey: string | null,
  violations: readonly ConstraintViolationDetail[] | null,
): boolean {
  if (locatedKey === null || violations === null) {
    return false;
  }
  return !violations.some((violation) => violationIdentityKey(violation) === locatedKey);
}
