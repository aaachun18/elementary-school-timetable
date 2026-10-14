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

// Task 68: GET /schedule-versions/{id}/check (Task 61) -- a read-only Hard
// Constraint check of a version's CURRENT Schedule rows. Mirrors
// backend/app/schemas/scheduler.py::ScheduleCheckResult. Besides the
// engine's H1-H9/H11/H12 types, `violations` can contain the service-level
// INCOMPLETE_SCHEDULE_ROW (Task 62) and FIXED_TIME_SLOT_MISMATCH (Task 66).
export interface ScheduleCheckResult {
  schedule_version_id: number;
  is_valid: boolean;
  violation_count: number;
  violations: ConstraintViolationDetail[];
}

// --- Task 69: manual timetable adjustment (Task 65 endpoints) ---

// POST /schedule-versions/{id}/move-lesson. target_room_id omitted/null =
// room unchanged.
export interface MoveLessonRequest {
  schedule_id: number;
  target_time_slot_id: number;
  target_room_id?: number | null;
  dry_run?: boolean;
}

// POST /schedule-versions/{id}/swap-lessons. Only the two rows' time slots
// are exchanged; each keeps its own teacher and room.
export interface SwapLessonsRequest {
  schedule_id: number;
  swap_with_schedule_id: number;
  dry_run?: boolean;
}

// One Schedule row that actually changed (unchanged rows are not listed).
export interface ScheduleChangeDetail {
  schedule_id: number;
  previous_time_slot_id: number | null;
  new_time_slot_id: number | null;
  previous_room_id: number | null;
  new_room_id: number | null;
}

// 200 response of both endpoints. `check` is the WHOLE version's check
// after the change (including problems that existed before it); with
// dry_run nothing was saved and this is what would happen.
export interface ScheduleAdjustmentResult {
  schedule_version_id: number;
  dry_run: boolean;
  changes: ScheduleChangeDetail[];
  check: ScheduleCheckResult;
}
