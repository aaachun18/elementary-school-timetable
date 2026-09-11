"""Tests for the Backtracking Scheduler
(scheduling_engine/algorithms/backtracking.py). Pure Python, no database,
no db_session/client fixtures."""

from scheduling_engine.algorithms.backtracking import schedule_backtracking
from scheduling_engine.algorithms.greedy import schedule_greedy
from scheduling_engine.algorithms.resources import SchedulingResources
from scheduling_engine.models.domain import (
    LessonAssignment,
    RequiredTeacherRule,
    RequirementPeriods,
    RoomInfo,
    RoomTypeRequirement,
    TeacherQualification,
    TeacherUnavailability,
    TeacherWorkloadLimit,
    TimeSlotInfo,
)


def _pending_lesson(
    lesson_id: int,
    class_subject_requirement_id: int,
    class_id: int,
    subject_id: int,
) -> LessonAssignment:
    return LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=class_subject_requirement_id,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=None,
        time_slot_id=None,
        room_id=None,
    )


def _empty_resources(**overrides: object) -> SchedulingResources:
    base = dict(
        time_slot_ids=[],
        teacher_qualifications=[],
        teacher_unavailability=[],
        required_teacher_rules=[],
        room_type_requirements=[],
        rooms=[],
        time_slots=[],
        active_statuses=[],
        requirement_periods=[],
        teacher_workload_limits=[],
    )
    base.update(overrides)
    return SchedulingResources(**base)  # type: ignore[arg-type]


# --- Success with ample resources: equivalent to the Greedy path ---


def test_backtracking_succeeds_with_ample_resources_and_zero_backtracks() -> None:
    lessons = [
        _pending_lesson(
            lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
        ),
        _pending_lesson(
            lesson_id=2, class_subject_requirement_id=2, class_id=1, subject_id=20
        ),
    ]
    resources = _empty_resources(
        time_slot_ids=[100, 200],
        teacher_qualifications=[
            TeacherQualification(teacher_id=1, subject_id=10),
            TeacherQualification(teacher_id=1, subject_id=20),
        ],
        time_slots=[
            TimeSlotInfo(time_slot_id=100, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=200, is_teaching_period=True),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=2, weekly_periods=1),
        ],
    )

    result = schedule_backtracking(lessons, resources)

    assert result.success is True
    assert result.state is not None
    assert result.failure_type is None
    assert result.backtrack_count == 0
    assert len(result.state.assignments) == 2


# --- The key scenario: Greedy fails, Backtracking recovers via retraction ---


def test_backtracking_succeeds_where_greedy_fails() -> None:
    # Only one room of the required type exists, so lessons A and B (both
    # needing that room, at overlapping-but-not-identical availability)
    # compete for it. A single-teacher, single-room-type-candidate design
    # for both, so neither Greedy nor Backtracking has any OTHER teacher
    # to fall back on -- the only way to reconcile them is for A to use a
    # DIFFERENT time slot than the one it tries first.
    lesson_a = _pending_lesson(
        lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
    )
    lesson_b = _pending_lesson(
        lesson_id=2, class_subject_requirement_id=2, class_id=2, subject_id=20
    )

    resources = _empty_resources(
        time_slot_ids=[100, 200],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=10),
            RequiredTeacherRule(class_subject_requirement_id=2, required_teacher_id=11),
        ],
        teacher_qualifications=[
            TeacherQualification(teacher_id=10, subject_id=10),
            TeacherQualification(teacher_id=11, subject_id=20),
        ],
        teacher_unavailability=[
            # Teacher 11 (lesson B) can ONLY use slot 100.
            TeacherUnavailability(teacher_id=11, time_slot_id=200),
        ],
        room_type_requirements=[
            RoomTypeRequirement(class_subject_requirement_id=1, required_room_type="特別教室"),
            RoomTypeRequirement(class_subject_requirement_id=2, required_room_type="特別教室"),
        ],
        rooms=[RoomInfo(room_id=500, room_type="特別教室")],  # only ONE such room
        time_slots=[
            TimeSlotInfo(time_slot_id=100, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=200, is_teaching_period=True),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=2, weekly_periods=1),
        ],
    )
    lessons = [lesson_a, lesson_b]

    # Prove Greedy actually fails on this exact input: A (processed first,
    # tied MRV count, input order preserved) greedily claims the only
    # room at slot 100 -- its first-tried candidate -- leaving B stuck: B
    # can only use slot 100 (teacher 11 unavailable at 200), but the room
    # there is taken, and there's no other candidate for B at all.
    greedy_result = schedule_greedy(lessons, resources)
    assert greedy_result.success is False

    # Backtracking retracts A's first choice and tries A's next candidate
    # (same teacher, slot 200 instead) -- freeing up the room at slot 100
    # for B.
    result = schedule_backtracking(lessons, resources)

    assert result.success is True
    assert result.state is not None
    assert result.backtrack_count >= 1
    assignment_by_lesson = {a.lesson_id: a for a in result.state.assignments}
    assert assignment_by_lesson[2].time_slot_id == 100
    assert assignment_by_lesson[1].time_slot_id == 200
    assert assignment_by_lesson[1].room_id == 500
    assert assignment_by_lesson[2].room_id == 500


# --- H8 real-time filtering: no backtracking needed at all ---


def test_backtracking_filters_out_overloaded_teacher_in_real_time() -> None:
    lesson_1 = _pending_lesson(
        lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
    )
    lesson_2 = _pending_lesson(
        lesson_id=2, class_subject_requirement_id=2, class_id=2, subject_id=20
    )

    resources = _empty_resources(
        time_slot_ids=[100, 200],
        teacher_qualifications=[
            TeacherQualification(teacher_id=10, subject_id=10),
            # Teacher 10 tried first for subject 20 too, but is already at
            # capacity from lesson_1 by the time lesson_2 is attempted.
            TeacherQualification(teacher_id=10, subject_id=20),
            TeacherQualification(teacher_id=11, subject_id=20),
        ],
        teacher_workload_limits=[
            TeacherWorkloadLimit(teacher_id=10, max_weekly_periods=1)
        ],
        time_slots=[
            TimeSlotInfo(time_slot_id=100, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=200, is_teaching_period=True),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=2, weekly_periods=1),
        ],
    )

    result = schedule_backtracking([lesson_1, lesson_2], resources)

    assert result.success is True
    # No conflict ever needed resolving via retraction -- H8 filtering
    # steered lesson_2 away from teacher 10 on the first attempt.
    assert result.backtrack_count == 0
    assignment_by_lesson = {a.lesson_id: a for a in result.state.assignments}
    assert assignment_by_lesson[1].teacher_id == 10
    assert assignment_by_lesson[2].teacher_id == 11


# --- Genuinely infeasible: exhausts the whole (small) search space ---


def test_backtracking_reports_definitely_infeasible() -> None:
    # Two lessons, SAME class, but only one time slot exists at all -- H2
    # (class conflict) makes it structurally impossible for both to be
    # scheduled, no matter which teacher/room is tried.
    lesson_a = _pending_lesson(
        lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
    )
    lesson_b = _pending_lesson(
        lesson_id=2, class_subject_requirement_id=2, class_id=1, subject_id=20
    )

    resources = _empty_resources(
        time_slot_ids=[100],
        teacher_qualifications=[
            TeacherQualification(teacher_id=1, subject_id=10),
            TeacherQualification(teacher_id=2, subject_id=20),
        ],
        time_slots=[TimeSlotInfo(time_slot_id=100, is_teaching_period=True)],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=2, weekly_periods=1),
        ],
    )

    result = schedule_backtracking([lesson_a, lesson_b], resources)

    assert result.success is False
    assert result.state is None
    assert result.failure_type == "DEFINITELY_INFEASIBLE"


def test_backtracking_reports_definitely_infeasible_for_missing_qualification() -> None:
    # Pre-flight case: zero candidate teachers at all, checked before any
    # search happens.
    lesson = _pending_lesson(
        lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=99
    )
    resources = _empty_resources(
        time_slot_ids=[100],
        time_slots=[TimeSlotInfo(time_slot_id=100, is_teaching_period=True)],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1)
        ],
    )

    result = schedule_backtracking([lesson], resources)

    assert result.success is False
    assert result.state is None
    assert result.failure_type == "DEFINITELY_INFEASIBLE"
    assert result.backtrack_count == 0
    assert len(result.lesson_failures) == 1
    assert result.lesson_failures[0].reasons[0].type == "NO_CANDIDATE_TEACHER"


def test_backtracking_reports_required_teacher_not_qualified() -> None:
    """Task 22 regression: a required-teacher rule (H6) naming a teacher
    who lacks the H5 qualification for this subject used to slip past the
    pre-flight "zero candidates" check (candidate_teacher_ids returned the
    required teacher as a candidate regardless of qualification), so the
    search would exhaust itself and report DEFINITELY_INFEASIBLE with an
    EMPTY lesson_failures list -- no explanation at all. This must now be
    caught up front, same as any other zero-candidate Lesson.
    """
    lesson = _pending_lesson(
        lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=8
    )
    resources = _empty_resources(
        time_slot_ids=[100],
        time_slots=[TimeSlotInfo(time_slot_id=100, is_teaching_period=True)],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=6)
        ],
        # Teacher 6 exists and is qualified for OTHER subjects, but not 8.
        teacher_qualifications=[
            TeacherQualification(teacher_id=6, subject_id=9),
            TeacherQualification(teacher_id=6, subject_id=10),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1)
        ],
    )

    result = schedule_backtracking([lesson], resources)

    assert result.success is False
    assert result.state is None
    assert result.failure_type == "DEFINITELY_INFEASIBLE"
    assert result.backtrack_count == 0
    assert len(result.lesson_failures) == 1
    reason = result.lesson_failures[0].reasons[0]
    assert reason.type == "H6_REQUIRED_TEACHER_NOT_QUALIFIED"
    assert reason.teacher_id == 6


# --- Search limits: distinct from "definitely infeasible" ---


def test_backtracking_reports_search_limit_exceeded_not_infeasible() -> None:
    # Reuse the exact scenario that DOES have a solution (and needs >= 1
    # backtrack to find it), but cap max_backtrack_steps at 0 so the run
    # is forced to abort at the very first backtrack instead of finding
    # it.
    lesson_a = _pending_lesson(
        lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
    )
    lesson_b = _pending_lesson(
        lesson_id=2, class_subject_requirement_id=2, class_id=2, subject_id=20
    )
    resources = _empty_resources(
        time_slot_ids=[100, 200],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=10),
            RequiredTeacherRule(class_subject_requirement_id=2, required_teacher_id=11),
        ],
        teacher_qualifications=[
            TeacherQualification(teacher_id=10, subject_id=10),
            TeacherQualification(teacher_id=11, subject_id=20),
        ],
        teacher_unavailability=[
            TeacherUnavailability(teacher_id=11, time_slot_id=200),
        ],
        room_type_requirements=[
            RoomTypeRequirement(class_subject_requirement_id=1, required_room_type="特別教室"),
            RoomTypeRequirement(class_subject_requirement_id=2, required_room_type="特別教室"),
        ],
        rooms=[RoomInfo(room_id=500, room_type="特別教室")],
        time_slots=[
            TimeSlotInfo(time_slot_id=100, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=200, is_teaching_period=True),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=2, weekly_periods=1),
        ],
    )
    lessons = [lesson_a, lesson_b]

    # Confirm it genuinely succeeds with the default limit first.
    unrestricted = schedule_backtracking(lessons, resources)
    assert unrestricted.success is True
    assert unrestricted.backtrack_count >= 1

    # Same input, artificially starved of search budget: max_backtrack_
    # steps=0 must mean ZERO backtracks are ever performed, not "one free
    # backtrack before giving up".
    restricted = schedule_backtracking(lessons, resources, max_backtrack_steps=0)

    assert restricted.success is False
    assert restricted.state is None
    assert restricted.failure_type == "SEARCH_LIMIT_EXCEEDED"
    assert restricted.backtrack_count == 0


def test_backtracking_max_backtrack_steps_boundary_is_exact() -> None:
    """max_backtrack_steps=N must allow EXACTLY N backtracks to happen (not
    N-1, not N+1): passing the natural backtrack_count K a solvable run
    needs should still succeed at max_backtrack_steps=K, but the same
    input with max_backtrack_steps=K-1 should be refused at the (K)th
    backtrack attempt, with backtrack_count left at exactly K-1 (not K)
    since that Kth backtrack was refused, not performed.

    Uses a 3-lesson chain (each pinned to a different required teacher,
    all three needing the one shared special room, with staggered teacher
    availability) that needs more than a single backtrack to resolve, so
    this isn't just re-testing the trivial 0-vs-1 boundary.
    """
    lesson_a = _pending_lesson(
        lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
    )
    lesson_b = _pending_lesson(
        lesson_id=2, class_subject_requirement_id=2, class_id=2, subject_id=20
    )
    lesson_c = _pending_lesson(
        lesson_id=3, class_subject_requirement_id=3, class_id=3, subject_id=30
    )
    resources = _empty_resources(
        time_slot_ids=[100, 200, 300],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=1),
            RequiredTeacherRule(class_subject_requirement_id=2, required_teacher_id=2),
            RequiredTeacherRule(class_subject_requirement_id=3, required_teacher_id=3),
        ],
        teacher_qualifications=[
            TeacherQualification(teacher_id=1, subject_id=10),
            TeacherQualification(teacher_id=2, subject_id=20),
            TeacherQualification(teacher_id=3, subject_id=30),
        ],
        teacher_unavailability=[
            # Teacher 1 (lesson A) is unrestricted.
            # Teacher 2 (lesson B) can ONLY use slot 100.
            TeacherUnavailability(teacher_id=2, time_slot_id=200),
            TeacherUnavailability(teacher_id=2, time_slot_id=300),
            # Teacher 3 (lesson C) can ONLY use slot 200.
            TeacherUnavailability(teacher_id=3, time_slot_id=100),
            TeacherUnavailability(teacher_id=3, time_slot_id=300),
        ],
        room_type_requirements=[
            RoomTypeRequirement(class_subject_requirement_id=1, required_room_type="特別教室"),
            RoomTypeRequirement(class_subject_requirement_id=2, required_room_type="特別教室"),
            RoomTypeRequirement(class_subject_requirement_id=3, required_room_type="特別教室"),
        ],
        rooms=[RoomInfo(room_id=500, room_type="特別教室")],  # only ONE shared room
        time_slots=[
            TimeSlotInfo(time_slot_id=100, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=200, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=300, is_teaching_period=True),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=2, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=3, weekly_periods=1),
        ],
    )
    lessons = [lesson_a, lesson_b, lesson_c]

    # Discover how many backtracks this scenario genuinely needs.
    unrestricted = schedule_backtracking(lessons, resources)
    assert unrestricted.success is True
    needed = unrestricted.backtrack_count
    assert needed >= 2, "scenario should need more than a single backtrack"

    # Exactly enough budget: still succeeds, using exactly `needed`.
    exact = schedule_backtracking(lessons, resources, max_backtrack_steps=needed)
    assert exact.success is True
    assert exact.backtrack_count == needed

    # One less than needed: must fail at the boundary, having performed
    # exactly `needed - 1` backtracks (the final, necessary one is
    # refused, not silently allowed through).
    one_short = schedule_backtracking(
        lessons, resources, max_backtrack_steps=needed - 1
    )
    assert one_short.success is False
    assert one_short.state is None
    assert one_short.failure_type == "SEARCH_LIMIT_EXCEEDED"
    assert one_short.backtrack_count == needed - 1


def test_backtracking_reports_timeout_not_infeasible() -> None:
    lesson_a = _pending_lesson(
        lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
    )
    lesson_b = _pending_lesson(
        lesson_id=2, class_subject_requirement_id=2, class_id=2, subject_id=20
    )
    resources = _empty_resources(
        time_slot_ids=[100, 200],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=10),
            RequiredTeacherRule(class_subject_requirement_id=2, required_teacher_id=11),
        ],
        teacher_qualifications=[
            TeacherQualification(teacher_id=10, subject_id=10),
            TeacherQualification(teacher_id=11, subject_id=20),
        ],
        teacher_unavailability=[
            TeacherUnavailability(teacher_id=11, time_slot_id=200),
        ],
        room_type_requirements=[
            RoomTypeRequirement(class_subject_requirement_id=1, required_room_type="特別教室"),
            RoomTypeRequirement(class_subject_requirement_id=2, required_room_type="特別教室"),
        ],
        rooms=[RoomInfo(room_id=500, room_type="特別教室")],
        time_slots=[
            TimeSlotInfo(time_slot_id=100, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=200, is_teaching_period=True),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=2, weekly_periods=1),
        ],
    )

    result = schedule_backtracking(
        [lesson_a, lesson_b], resources, timeout_seconds=0.0
    )

    assert result.success is False
    assert result.state is None
    assert result.failure_type == "TIMEOUT"


# --- H7: still whole-batch/post-hoc, same as Greedy ---


def test_backtracking_detects_h7_violation_when_lesson_count_is_short() -> None:
    lesson = _pending_lesson(
        lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
    )
    resources = _empty_resources(
        time_slot_ids=[100],
        teacher_qualifications=[TeacherQualification(teacher_id=1, subject_id=10)],
        time_slots=[TimeSlotInfo(time_slot_id=100, is_teaching_period=True)],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=2)
        ],
    )

    result = schedule_backtracking([lesson], resources)

    assert result.success is False
    assert result.state is None
    assert result.failure_type is None
    assert len(result.post_hoc_violations) == 1
    assert result.post_hoc_violations[0].type == "H7_WEEKLY_PERIODS"
