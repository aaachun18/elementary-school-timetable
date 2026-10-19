// Task 68/69: where 「在課表中查看」 takes the user for one violation -- which
// timetable view, and whose timetable. Pure function, no React.

import type { ConstraintViolationDetail } from "../types/scheduler";
import { resolveInactiveEntities, type NameLookups } from "./failureDiagnostics";

export type TimetableViewMode = "class" | "teacher" | "room";

export interface LocateTarget {
  viewMode: TimetableViewMode;
  targetId: number;
}

// Task 69: the view in which each type's problem is most visible. A
// teacher's double booking (H1) only shows as one ⚠️ cell in that teacher's
// own timetable -- in either class's timetable it looks like an ordinary
// lesson. Types not listed here (H7, INCOMPLETE_SCHEDULE_ROW,
// FIXED_TIME_SLOT_MISMATCH, H12 -- see below -- and any future type) use
// locateByFields().
const VIEW_BY_TYPE: Record<string, TimetableViewMode> = {
  H1_TEACHER_CONFLICT: "teacher",
  H4_TEACHER_AVAILABILITY: "teacher",
  H5_TEACHER_QUALIFICATION: "teacher",
  H6_REQUIRED_TEACHER: "teacher",
  H8_TEACHER_MAX_WORKLOAD: "teacher",
  H2_CLASS_CONFLICT: "class",
  H11_NON_TEACHING_PERIOD: "class",
  H3_ROOM_CONFLICT: "room",
  H9_ROOM_TYPE: "room",
  // Task 90: a lesson block is the class's; a minimum workload the teacher's.
  BLOCK_NOT_CONSECUTIVE: "class",
  BLOCK_SAME_DAY: "class",
  TEACHER_MIN_WORKLOAD: "teacher",
  // Task 94: the lesson has no room, so it shows in its class's timetable.
  ROOM_MISSING_FOR_TYPE: "class",
};

// H12 names a lesson involving SOMETHING inactive -- the view follows
// whichever entity actually is (the same one its sentence names first). An
// inactive subject has no view of its own, so it shows in the class's.
const VIEW_BY_INACTIVE_ENTITY_TAB = {
  teachers: "teacher",
  classes: "class",
  subjects: "class",
  rooms: "room",
} as const;

function idForView(
  violation: ConstraintViolationDetail,
  viewMode: TimetableViewMode,
): number | null {
  if (viewMode === "teacher") {
    return violation.teacher_id;
  }
  if (viewMode === "room") {
    return violation.room_id;
  }
  return violation.class_id;
}

// Task 68's rule, still the fallback: a class (or, for H7, which only names
// a requirement, that requirement's class) wins over a teacher, which wins
// over a room.
function locateByFields(
  violation: ConstraintViolationDetail,
  lookups: NameLookups,
): LocateTarget | null {
  const classId =
    violation.class_id ??
    (violation.class_subject_requirement_id === null
      ? null
      : (lookups.requirementById.get(violation.class_subject_requirement_id)?.class_id ?? null));
  if (classId !== null) {
    return { viewMode: "class", targetId: classId };
  }
  if (violation.teacher_id !== null) {
    return { viewMode: "teacher", targetId: violation.teacher_id };
  }
  if (violation.room_id !== null) {
    return { viewMode: "room", targetId: violation.room_id };
  }
  return null;
}

function preferredViewMode(
  violation: ConstraintViolationDetail,
  lookups: NameLookups,
): TimetableViewMode | undefined {
  if (violation.type === "H12_ACTIVE_STATUS") {
    const [firstInactive] = resolveInactiveEntities(violation, lookups);
    return firstInactive === undefined ? undefined : VIEW_BY_INACTIVE_ENTITY_TAB[firstInactive.tab];
  }
  return VIEW_BY_TYPE[violation.type];
}

// The type decides the view; if the id that view needs is missing on this
// violation, fall back to locateByFields(). null = nothing to show.
export function resolveLocateTarget(
  violation: ConstraintViolationDetail,
  lookups: NameLookups,
): LocateTarget | null {
  const viewMode = preferredViewMode(violation, lookups);
  if (viewMode !== undefined) {
    const targetId = idForView(violation, viewMode);
    if (targetId !== null) {
      return { viewMode, targetId };
    }
  }
  return locateByFields(violation, lookups);
}
