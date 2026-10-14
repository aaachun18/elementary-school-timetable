// Task 71: where a lesson can be moved or dropped in the timetable's edit
// mode. canMoveLessonTo() is shared by the click flow (where 「移到這裡」
// appears) and drag & drop, so both offer the same target cells. Pure
// functions, no React.

import type { EnrichedSchedule } from "../hooks/useTimetableData";
import type { TimeSlot } from "../types/timeSlot";

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
