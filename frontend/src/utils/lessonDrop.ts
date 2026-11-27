// Task 71: where a lesson can be moved or dropped in the timetable's edit
// mode. canMoveLessonTo() is shared by the click flow (where 「移到這裡」
// appears) and drag & drop, so both offer the same target cells. Pure
// functions, no React.

import type { EnrichedSchedule } from "../hooks/useTimetableData";
import type { TimeSlot } from "../types/timeSlot";
import type { TimetableViewMode } from "./violationLocate";

// A class's own classroom (原班教室) has no Room record -- 原班上課 is a
// lesson with no room -- yet the room view lists one per class. Its id there
// is the class id negated, which can never be a real room id.
export function homeroomTargetId(classId: number): number {
  return -classId;
}

// The id a lesson is listed under in each view: its class, teacher or room
// (Task 84: moved here from TimetableGrid so the page can tell whether a
// lesson is on the grid being shown). A lesson without a room is in its
// class's own classroom.
export function lessonTargetId(lesson: EnrichedSchedule, viewMode: TimetableViewMode): number | null {
  if (viewMode === "class") {
    return lesson.classId;
  }
  if (viewMode === "teacher") {
    return lesson.teacherId;
  }
  return lesson.roomId ?? homeroomTargetId(lesson.classId);
}

// A real teaching TimeSlot other than the lesson's current one. A cell with
// no TimeSlot record has no id to move to; a non-teaching period (lunch,
// early study hall...) is never a target; the lesson's own slot would be no
// change at all.
export function canMoveLessonTo(
  lesson: EnrichedSchedule,
  timeSlot: TimeSlot | undefined,
): timeSlot is TimeSlot {
  return (
    timeSlot !== undefined && timeSlot.is_teaching_period && timeSlot.id !== lesson.timeSlotId
  );
}

// Any other lesson in a different time slot. Two lessons already in the
// same slot (e.g. a double booking in one cell) would swap nothing.
export function canSwapLessons(lesson: EnrichedSchedule, other: EnrichedSchedule): boolean {
  return other.scheduleId !== lesson.scheduleId && other.timeSlotId !== lesson.timeSlotId;
}

// Task 103 (bug fix): which lesson a drop is about. The grid remembers the
// lesson it saw start the drag (`dragged`) -- the same one its drop hints
// were drawn for -- and that wins; the drag's own data (dataTransfer
// "text/plain", the scheduleId) is only a fallback. Reading only the drag
// data failed in some browsers: the hint said 「移到這裡」 but the drop could
// not tell which lesson it was, so nothing happened. A lesson no longer in
// the timetable (it reloaded meanwhile) is no lesson.
export function pickDraggedLesson<T extends { scheduleId: number }>(
  dragged: T | null,
  dragDataText: string,
  schedules: readonly T[],
): T | undefined {
  if (dragged !== null) {
    return schedules.find((schedule) => schedule.scheduleId === dragged.scheduleId);
  }
  if (dragDataText.trim() === "") {
    return undefined;
  }
  const scheduleId = Number(dragDataText);
  return Number.isInteger(scheduleId)
    ? schedules.find((schedule) => schedule.scheduleId === scheduleId)
    : undefined;
}
