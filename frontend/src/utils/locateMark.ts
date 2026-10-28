// Task 100 (item 6): the amber 「在課表中查看」 mark -- whether it is still
// shown. Pure, no React (locateMark.test.ts).
//
// The mark remembers where it was made: the record (a working copy has its
// own id), edit mode or not, and the grid being shown. It is shown only
// while all of that is unchanged AND the problem behind it is not known
// to be gone. So saving (the working copy is replaced by the saved record
// and edit mode ends), switching record, leaving edit mode and switching
// class / teacher / room each hide it, even where no check result exists
// yet -- the gap that left the mark on a freshly saved timetable.

import { isLocatedProblemGone } from "./adjustmentRefresh";
import type { TimetableViewMode } from "./violationLocate";
import type { ConstraintViolationDetail } from "../types/scheduler";

export interface LocateMark {
  timeSlotId: number;
  // violationIdentityKey of the located problem.
  problemKey: string;
  versionId: number;
  isEditing: boolean;
  viewMode: TimetableViewMode;
  targetId: number;
}

// What the page shows right now.
export interface LocateContext {
  versionId: number | null;
  isEditing: boolean;
  viewMode: TimetableViewMode;
  targetId: number | null;
}

// The TimeSlot to mark, or null.
export function visibleLocateSlot(
  mark: LocateMark | null,
  context: LocateContext,
  violations: readonly ConstraintViolationDetail[] | null,
): number | null {
  if (mark === null) {
    return null;
  }
  const isSameView =
    mark.versionId === context.versionId &&
    mark.isEditing === context.isEditing &&
    mark.viewMode === context.viewMode &&
    mark.targetId === context.targetId;
  if (!isSameView || isLocatedProblemGone(mark.problemKey, violations)) {
    return null;
  }
  return mark.timeSlotId;
}
