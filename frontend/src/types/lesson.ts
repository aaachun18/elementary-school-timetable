// Mirrors backend/app/schemas/lesson.py::LessonRead in full, including
// Task 28's fixed_time_slot_id. Lesson has no create/update/remove
// endpoints on the backend (rows are only produced by generate-lessons),
// so there are no corresponding Create/Update interfaces here -- unlike
// every other resource module, a full 5-set would describe endpoints that
// don't exist.

export interface Lesson {
  id: number;
  class_subject_requirement_id: number;
  sequence_number: number;
  fixed_time_slot_id: number | null;
  created_at: string;
  updated_at: string;
}

// Body for PATCH /lessons/{id}/fix-time-slot (Task 28).
export interface LessonFixTimeSlot {
  time_slot_id: number | null;
}
