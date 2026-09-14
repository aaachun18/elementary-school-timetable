// Mirrors backend/app/schemas/schedule_version.py's generate-lessons types
// and backend/app/schemas/scheduler.py's run-scheduler types, in full.

export interface GeneratedLessonInfo {
  lesson_id: number;
  class_subject_requirement_id: number;
  sequence_number: number;
}

// Task 32.8: created_count is only how many NEW Lesson rows THIS call
// inserted -- calling generate-lessons again on an already-synced version
// correctly returns created_count=0 (idempotent diff-sync), which is NOT
// the same as "there are 0 lessons". total_lesson_count is the actual
// current total for the version's semester; that's the number to display
// as "共 X 堂課待排", never created_count.
export interface GenerateLessonsResponse {
  created_lessons: GeneratedLessonInfo[];
  created_count: number;
  total_lesson_count: number;
}

export interface RunSchedulerSuccessResponse {
  scheduled_count: number;
  backtrack_count: number;
}

// Mirrors scheduling_engine.constraints.base.ConstraintViolation via
// backend/app/schemas/scheduler.py::ConstraintViolationDetail. Task 32 only
// needs to know a failure happened; this is defined in full now so the
// next Task (failure diagnosis) doesn't have to touch the API/type layer
// at all, only the rendering.
export interface ConstraintViolationDetail {
  type: string;
  severity: string;
  lesson_id: number | null;
  teacher_id: number | null;
  class_id: number | null;
  subject_id: number | null;
  time_slot_id: number | null;
  message: string;
  suggested_action: string | null;
  room_id: number | null;
  class_subject_requirement_id: number | null;
}

export interface LessonFailureDetail {
  lesson_id: number;
  class_subject_requirement_id: number;
  reasons: ConstraintViolationDetail[];
}

export type SchedulerFailureType =
  | "DEFINITELY_INFEASIBLE"
  | "SEARCH_LIMIT_EXCEEDED"
  | "TIMEOUT"
  | "REQUIREMENT_PERIODS_MISMATCH"
  | "STATIC_CHECK_FAILED";

export interface RunSchedulerFailureResponse {
  failure_type: SchedulerFailureType;
  lesson_failures: LessonFailureDetail[];
  post_hoc_violations: ConstraintViolationDetail[];
  backtrack_count: number;
}
