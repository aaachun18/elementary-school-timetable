from typing import Literal

from pydantic import BaseModel, ConfigDict


class ConstraintViolationDetail(BaseModel):
    """Serializable mirror of scheduling_engine.constraints.base.ConstraintViolation.

    model_config lets this be built directly from the dataclass instance via
    model_validate(violation) -- no manual field-by-field copying needed.
    severity is a plain str here (Severity is itself a str Enum on the
    engine side, so this loses nothing) since Pydantic has no reason to know
    about the engine's own Enum type.
    """

    model_config = ConfigDict(from_attributes=True)

    type: str
    severity: str
    lesson_id: int | None
    teacher_id: int | None
    class_id: int | None
    subject_id: int | None
    time_slot_id: int | None
    message: str
    suggested_action: str | None = None
    room_id: int | None = None
    class_subject_requirement_id: int | None = None
    # Task 88: see ConstraintViolation -- block_no for lesson-block
    # violations, identity_key (stable across a move; set by the newer
    # types only) and schedule_id (filled in by the schedule check).
    block_no: int | None = None
    identity_key: str | None = None
    schedule_id: int | None = None


class LessonFailureDetail(BaseModel):
    """Serializable mirror of scheduling_engine.algorithms.resources.LessonFailure."""

    model_config = ConfigDict(from_attributes=True)

    lesson_id: int
    class_subject_requirement_id: int
    reasons: list[ConstraintViolationDetail]


class SchedulerRunResult(BaseModel):
    """200 response: the scheduler placed every Lesson successfully."""

    scheduled_count: int
    backtrack_count: int


class SchedulerFailureDetail(BaseModel):
    """422 response body. failure_type mirrors
    scheduling_engine.algorithms.backtracking.BacktrackingResult.failure_type,
    plus two extra cases that aren't search-level BacktrackingResult
    outcomes at all:
    - "REQUIREMENT_PERIODS_MISMATCH": every Lesson placed fine, but the
      finished schedule still fails the post-hoc H7 check -- that case
      leaves BacktrackingResult.failure_type as None, so it needs its own
      label here to avoid reporting a misleading null failure_type.
    - "STATIC_CHECK_FAILED" (Task 23; 4th check added Task 38): the
      pre-search static feasibility check (teacher workload / teacher
      availability / inactive entities / a Lesson with zero candidate
      teachers at all) found a problem BEFORE schedule_backtracking() was
      ever called -- backtrack_count is always 0 for this case, since no
      search ran at all. Unlike the other 4 failure_type values,
      lesson_failures and post_hoc_violations can BOTH be non-empty here at
      once: the zero-candidate-teacher check is inherently per-Lesson
      (lesson_failures) while the other three are whole-batch
      (post_hoc_violations), and check_static_feasibility() always reports
      everything all four checks found, not just whichever fired first.
    """

    failure_type: Literal[
        "DEFINITELY_INFEASIBLE",
        "SEARCH_LIMIT_EXCEEDED",
        "TIMEOUT",
        "REQUIREMENT_PERIODS_MISMATCH",
        "STATIC_CHECK_FAILED",
    ]
    lesson_failures: list[LessonFailureDetail]
    post_hoc_violations: list[ConstraintViolationDetail]
    backtrack_count: int


class ScheduleCheckResult(BaseModel):
    """Task 61: 200 response of GET /schedule-versions/{id}/check -- every
    Hard Constraint violation in the version's current Schedule rows.
    is_valid/violation_count are derived from `violations`, included so a
    caller doesn't have to compute them. violation_count counts every
    entry; is_valid is "no ERROR" -- Task 88's WARNING
    (TEACHER_MIN_WORKLOAD) is listed but leaves the timetable valid."""

    schedule_version_id: int
    is_valid: bool
    violation_count: int
    violations: list[ConstraintViolationDetail]


class TeacherReassignmentRequest(BaseModel):
    """Task 63: body of POST /schedule-versions/{id}/reassign-teacher."""

    class_subject_requirement_id: int
    new_teacher_id: int
    dry_run: bool = False


class TeacherReassignmentResult(BaseModel):
    """Task 63: 200 response of reassign-teacher. `check` is the version's
    full schedule check AFTER the change (for dry_run, the state the change
    would have produced -- nothing was saved)."""

    schedule_version_id: int
    class_subject_requirement_id: int
    previous_teacher_id: int | None
    new_teacher_id: int
    updated_schedule_row_count: int
    dry_run: bool
    check: ScheduleCheckResult


class MoveLessonRequest(BaseModel):
    """Task 65: body of POST /schedule-versions/{id}/move-lesson.
    target_room_id None (or omitted) keeps the current room -- this API
    cannot clear a room."""

    schedule_id: int
    target_time_slot_id: int
    target_room_id: int | None = None
    dry_run: bool = False


class SwapLessonsRequest(BaseModel):
    """Task 65: body of POST /schedule-versions/{id}/swap-lessons."""

    schedule_id: int
    swap_with_schedule_id: int
    dry_run: bool = False


class ScheduleChangeDetail(BaseModel):
    """Task 65: one Schedule row whose time slot and/or room changed."""

    model_config = ConfigDict(from_attributes=True)

    schedule_id: int
    previous_time_slot_id: int | None
    new_time_slot_id: int | None
    previous_room_id: int | None
    new_room_id: int | None


class ScheduleAdjustmentResult(BaseModel):
    """Task 65: 200 response of move-lesson and swap-lessons. `changes`
    lists only rows that actually changed (for dry_run: would change);
    `check` is the version's full schedule check after the change."""

    schedule_version_id: int
    dry_run: bool
    changes: list[ScheduleChangeDetail]
    check: ScheduleCheckResult


# --- Task 83: GET /schedule-versions/{id}/move-candidates/{schedule_id} ---


class BlockMemberDetail(BaseModel):
    """Task 89: one Schedule row that moves with a change involving a
    lesson block (連堂), and the time slot it goes to."""

    model_config = ConfigDict(from_attributes=True)

    schedule_id: int
    to_time_slot_id: int | None


class UnsupportedSwapDetail(BaseModel):
    """Task 89: a lesson in the slot that can't be swapped with under the
    block rules; reason is BLOCK_SWAP_UNSUPPORTED (what swap-lessons would
    answer with 409)."""

    model_config = ConfigDict(from_attributes=True)

    swap_with_schedule_id: int
    reason: str


class MoveCandidateSwap(BaseModel):
    """Swapping the lesson with this row (one in the candidate time slot
    that shares its class, teacher or room): the version's check after the
    swap -- what swap-lessons with dry_run would report. Task 89:
    block_members lists every row the swap moves (both whole groups) when a
    block is involved; null for two lessons of no block."""

    swap_with_schedule_id: int
    check: ScheduleCheckResult
    block_members: list[BlockMemberDetail] | None = None


class MoveCandidateSlot(BaseModel):
    """One time slot. available=False means it is not a move target, and
    `move` is null; unavailable_reason is NON_TEACHING_SLOT or CURRENT_SLOT,
    or (Task 89, a lesson in a block only) BLOCK_OUT_OF_RANGE -- the whole
    block doesn't fit into adjacent teaching periods of that day there --
    or BLOCK_TARGET_OCCUPIED -- the block would land on other lessons of
    its class (swap with them instead, if `swaps` offers it). `move` is the
    version's check after moving the lesson here (room unchanged) -- what
    move-lesson with dry_run would report. `swaps` lists every possible
    swap in this slot (possibly empty). Task 89: block_members (lesson in a
    block, available slot only) says where every lesson of the block goes;
    unsupported_swaps lists the lessons here a swap with is refused (null
    when none)."""

    time_slot_id: int
    available: bool
    unavailable_reason: str | None
    move: ScheduleCheckResult | None
    swaps: list[MoveCandidateSwap]
    block_members: list[BlockMemberDetail] | None = None
    unsupported_swaps: list[UnsupportedSwapDetail] | None = None


class MoveCandidatesResult(BaseModel):
    """baseline is the version's check as it stands (same as GET /check);
    candidates has one entry per time slot, in weekday/period order. The
    checks are complete lists, not differences -- the caller compares them
    with baseline itself (the frontend's diffViolations())."""

    schedule_version_id: int
    schedule_id: int
    current_time_slot_id: int | None
    baseline: ScheduleCheckResult
    candidates: list[MoveCandidateSlot]


# --- Task 92: unscheduled lessons and placing them (decision 28) ---


class EligibleTeacherDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    teacher_id: int
    name: str


class UnscheduledLessonDetail(BaseModel):
    """A lesson of the version's semester with no Schedule row in the
    version. suggested_room_id (Task 92B): with no room type, the class's
    homeroom (what place-lesson uses by default; null without one); with a
    room type, the first active room of that type. eligible_teachers: active teachers qualified for
    the subject, by name -- returned even when required_teacher_id is set."""

    model_config = ConfigDict(from_attributes=True)

    lesson_id: int
    class_subject_requirement_id: int
    class_id: int
    class_name: str
    subject_id: int
    subject_name: str
    sequence_number: int
    required_teacher_id: int | None
    block_no: int | None
    block_seq: int | None
    lesson_pattern: str | None
    fixed_time_slot_id: int | None
    suggested_room_id: int | None
    eligible_teachers: list[EligibleTeacherDetail]
    # Task 94 (additive): the requirement's room type; the room place-lesson
    # uses when no room_id is sent; and, with a room type, whether an
    # active room of exactly that type exists (null without a room type).
    room_type: str | None = None
    default_room_id: int | None = None
    has_matching_room: bool | None = None


class UnscheduledLessonsResult(BaseModel):
    """GET /schedule-versions/{id}/unscheduled-lessons: ordered by class,
    subject, block, place in the block."""

    schedule_version_id: int
    lessons: list[UnscheduledLessonDetail]


class PlaceLessonRequest(BaseModel):
    """POST /schedule-versions/{id}/place-lesson. teacher_id null: the
    requirement's required teacher (none -> 409 TEACHER_REQUIRED); room_id
    null: the class's homeroom for a requirement with no room type (Task
    92B), otherwise no room."""

    lesson_id: int
    time_slot_id: int
    teacher_id: int | None = None
    room_id: int | None = None
    dry_run: bool = False


class PlacementChangeDetail(BaseModel):
    """One new Schedule row. schedule_id is null for dry_run; previous_*
    are always null (the lesson had no row)."""

    model_config = ConfigDict(from_attributes=True)

    schedule_id: int | None
    lesson_id: int
    teacher_id: int
    previous_time_slot_id: int | None
    new_time_slot_id: int
    previous_room_id: int | None
    new_room_id: int | None


class PlaceLessonResult(BaseModel):
    """200 response of place-lesson: the rows placed (the lesson and the
    unplaced rest of its block) and the version's full check after."""

    schedule_version_id: int
    dry_run: bool
    changes: list[PlacementChangeDetail]
    check: ScheduleCheckResult


class PlacedLessonDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lesson_id: int
    to_time_slot_id: int


class PlaceCandidateSlot(BaseModel):
    """One time slot. available=False: unavailable_reason is
    NON_TEACHING_SLOT, BLOCK_OUT_OF_RANGE, BLOCK_TARGET_OCCUPIED or
    BLOCK_PARTIAL_MISMATCH and `check` is null. Otherwise `check` is what
    place-lesson with dry_run would report. block_members (a lesson of a
    block, available slot only): every lesson placed with it."""

    time_slot_id: int
    available: bool
    unavailable_reason: str | None
    check: ScheduleCheckResult | None
    block_members: list[PlacedLessonDetail] | None = None


class PlaceCandidatesResult(BaseModel):
    """GET /schedule-versions/{id}/place-candidates/{lesson_id}: teacher_id
    and room_id are the ones every candidate was checked with (resolved as
    place-lesson would); baseline is GET /check as it stands."""

    schedule_version_id: int
    lesson_id: int
    teacher_id: int
    room_id: int | None
    baseline: ScheduleCheckResult
    candidates: list[PlaceCandidateSlot]
