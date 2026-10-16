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
  // Task 90 (backend Task 88): optional -- older responses don't carry them.
  // block_no: which lesson block (連堂) of the requirement a BLOCK_*
  // violation is about. identity_key: "which problem is this", the same
  // before and after a move (set by the newer types only; see
  // utils/violationMerge.ts). schedule_id: the Schedule row of lesson_id
  // (filled in by GET /check and everything built on it).
  block_no?: number | null;
  identity_key?: string | null;
  schedule_id?: number | null;
}

// Task 90: ConstraintViolationDetail.severity. A WARNING (backend Task 88:
// TEACHER_MIN_WORKLOAD only, so far) is listed but never makes a timetable
// invalid -- ScheduleCheckResult.is_valid is "no ERROR".
export const SEVERITY_WARNING = "WARNING";

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

// --- Task 70: reassigning one course to another teacher (Task 63 endpoint) ---

// Body of POST /schedule-versions/{id}/reassign-teacher.
export interface TeacherReassignmentRequest {
  class_subject_requirement_id: number;
  new_teacher_id: number;
  dry_run?: boolean;
}

// 200 response. previous_teacher_id is the course's teacher in this version
// before the change (the one teacher on all its Schedule rows, otherwise the
// requirement's required teacher). updated_schedule_row_count counts only
// rows whose teacher actually changes. `check` is the whole version's check
// after the change (with dry_run: what saving would produce).
export interface TeacherReassignmentResult {
  schedule_version_id: number;
  class_subject_requirement_id: number;
  previous_teacher_id: number | null;
  new_teacher_id: number;
  updated_schedule_row_count: number;
  dry_run: boolean;
  check: ScheduleCheckResult;
}

// --- Task 84: GET /schedule-versions/{id}/move-candidates/{schedule_id}
// (Task 83; ADMIN + DRAFT only). Mirrors backend/app/schemas/scheduler.py's
// MoveCandidatesResult. Every check is a complete list, same as /check --
// the frontend compares it with `baseline` itself (diffViolations()). ---

// Task 90 (backend Task 89): one Schedule row that moves with a change of
// a lesson block (連堂), and where it goes.
export interface BlockMember {
  schedule_id: number;
  to_time_slot_id: number | null;
}

// Task 90: a lesson in the slot the selected one can't be swapped with
// under the block rules (reason: "BLOCK_SWAP_UNSUPPORTED").
export interface UnsupportedSwap {
  swap_with_schedule_id: number;
  reason: string;
}

// Swapping the lesson with this row: the version's check after the swap.
// Task 90: block_members -- every row the swap moves (both whole groups)
// when a block is involved; null/absent for two single lessons.
export interface MoveCandidateSwap {
  swap_with_schedule_id: number;
  check: ScheduleCheckResult;
  block_members?: BlockMember[] | null;
}

// One time slot. available=false ("NON_TEACHING_SLOT" / "CURRENT_SLOT", or
// -- Task 90, a lesson in a block -- "BLOCK_OUT_OF_RANGE" /
// "BLOCK_TARGET_OCCUPIED") means it is not a move target, and `move` is
// null. block_members: where every lesson of the selected lesson's block
// goes for this move (null/absent for a single lesson); unsupported_swaps:
// lessons here that can't be swapped with (null/absent when none).
export interface MoveCandidateSlot {
  time_slot_id: number;
  available: boolean;
  unavailable_reason: string | null;
  move: ScheduleCheckResult | null;
  swaps: MoveCandidateSwap[];
  block_members?: BlockMember[] | null;
  unsupported_swaps?: UnsupportedSwap[] | null;
}

// Task 90 (backend Task 89): the 409 body of move-lesson / swap-lessons
// when the lesson block rules refuse a change -- `detail` is Chinese,
// `reason` one of the BLOCK_* codes move-candidates also reports.
export interface BlockAdjustmentRefusal {
  detail: string;
  reason: string;
}

export interface MoveCandidatesResult {
  schedule_version_id: number;
  schedule_id: number;
  current_time_slot_id: number | null;
  baseline: ScheduleCheckResult;
  candidates: MoveCandidateSlot[];
}
