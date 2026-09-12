"""Tests for Task 28's Lesson.fixed_time_slot_id support in the scheduling
engine. Pure Python, no database, no db_session/client fixtures -- mirrors
the style of test_greedy.py / test_backtracking.py.

A "fixed" lesson is represented exactly as the rest of the engine already
represents a partially-filled Schedule row: the pending LessonAssignment
handed to schedule_greedy()/schedule_backtracking() has time_slot_id
already set (instead of None) -- see
scheduling_engine/algorithms/resources.py::candidate_time_slot_ids().
"""

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
    TimeSlotInfo,
)


def _lesson(
    lesson_id: int,
    class_subject_requirement_id: int,
    class_id: int,
    subject_id: int,
    fixed_time_slot_id: int | None = None,
) -> LessonAssignment:
    return LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=class_subject_requirement_id,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=None,
        time_slot_id=fixed_time_slot_id,
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


# --- Fixed slot is honored, not searched ---


def test_greedy_fixed_time_slot_is_locked_and_not_searched() -> None:
    # Slot 100 is listed FIRST and would normally be tried first -- fixing
    # this lesson to 200 must still win, proving it's a lock, not a
    # coincidental first choice.
    lesson = _lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=10, fixed_time_slot_id=200)
    resources = _empty_resources(
        time_slot_ids=[100, 200],
        teacher_qualifications=[TeacherQualification(teacher_id=1, subject_id=10)],
        time_slots=[
            TimeSlotInfo(time_slot_id=100, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=200, is_teaching_period=True),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1)
        ],
    )

    result = schedule_greedy([lesson], resources)

    assert result.success is True
    assert result.state is not None
    assert result.state.assignments[0].time_slot_id == 200


def test_backtracking_fixed_time_slot_is_locked_and_not_searched() -> None:
    lesson = _lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=10, fixed_time_slot_id=200)
    resources = _empty_resources(
        time_slot_ids=[100, 200],
        teacher_qualifications=[TeacherQualification(teacher_id=1, subject_id=10)],
        time_slots=[
            TimeSlotInfo(time_slot_id=100, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=200, is_teaching_period=True),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1)
        ],
    )

    result = schedule_backtracking([lesson], resources)

    assert result.success is True
    assert result.state is not None
    assert result.state.assignments[0].time_slot_id == 200
    assert result.backtrack_count == 0


# --- MRV integration: a fixed lesson is maximally constrained in the time
# dimension, same in spirit as a required_teacher_id pin on the teacher
# dimension, and must sort accordingly. ---


def test_greedy_mrv_prioritizes_fixed_time_slot_lesson() -> None:
    """Lesson A (flexible time, 1 qualified teacher) is listed FIRST but is
    LESS constrained overall than Lesson B (fixed time slot, 1 qualified
    teacher, and needs the one shared special room). Under the old
    "teacher-count-only" MRV key both would tie (each has exactly 1
    candidate teacher) and stable-sort would process A first -- which
    greedily claims the shared room at the only slot B can ever use,
    stranding B. The new teacher x time x room product key breaks the tie
    correctly (B's product is smaller, since its time dimension is pinned
    to a single value), so B goes first and the run succeeds without any
    backtracking at all.
    """
    lesson_a = _lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=10)
    lesson_b = _lesson(
        2, class_subject_requirement_id=2, class_id=2, subject_id=20, fixed_time_slot_id=100
    )

    resources = _empty_resources(
        time_slot_ids=[100, 200],
        teacher_qualifications=[
            TeacherQualification(teacher_id=10, subject_id=10),
            TeacherQualification(teacher_id=20, subject_id=20),
        ],
        room_type_requirements=[
            RoomTypeRequirement(class_subject_requirement_id=1, required_room_type="特別教室"),
            RoomTypeRequirement(class_subject_requirement_id=2, required_room_type="特別教室"),
        ],
        rooms=[RoomInfo(room_id=500, room_type="特別教室")],  # only one such room
        time_slots=[
            TimeSlotInfo(time_slot_id=100, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=200, is_teaching_period=True),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=2, weekly_periods=1),
        ],
    )

    result = schedule_greedy([lesson_a, lesson_b], resources)

    assert result.success is True
    assert result.state is not None
    assignment_by_lesson = {a.lesson_id: a for a in result.state.assignments}
    # B (fixed) got the room at its mandatory slot 100; A was pushed to 200.
    assert assignment_by_lesson[2].time_slot_id == 100
    assert assignment_by_lesson[2].room_id == 500
    assert assignment_by_lesson[1].time_slot_id == 200
    assert assignment_by_lesson[1].room_id == 500


def test_backtracking_succeeds_via_retraction_when_fixed_time_slot_forces_move() -> None:
    """Lesson A (required teacher, flexible time) and Lesson B (fixed time
    slot 100, 2 qualified teachers, no required-teacher pin) tie under the
    product-based MRV key (2 x 1 x 1 == 1 x 2 x 1), so input order (A then
    B) is preserved -- Greedy therefore still greedily claims the shared
    special room for A at slot 100 (A's first-tried candidate), leaving B
    permanently stuck (B's time is fixed to 100, and the room is now taken
    for that exact slot). Backtracking recovers by retracting A's choice
    and trying A's next candidate (slot 200 instead), freeing the room at
    100 for B.
    """
    lesson_a = _lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=10)
    lesson_b = _lesson(
        2, class_subject_requirement_id=2, class_id=2, subject_id=20, fixed_time_slot_id=100
    )

    resources = _empty_resources(
        time_slot_ids=[100, 200],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=10),
        ],
        teacher_qualifications=[
            TeacherQualification(teacher_id=10, subject_id=10),
            TeacherQualification(teacher_id=11, subject_id=20),
            TeacherQualification(teacher_id=12, subject_id=20),
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

    # Confirm Greedy actually fails on this exact input first.
    greedy_result = schedule_greedy(lessons, resources)
    assert greedy_result.success is False

    result = schedule_backtracking(lessons, resources)

    assert result.success is True
    assert result.state is not None
    assert result.backtrack_count >= 1
    assignment_by_lesson = {a.lesson_id: a for a in result.state.assignments}
    assert assignment_by_lesson[2].time_slot_id == 100
    assert assignment_by_lesson[2].room_id == 500
    assert assignment_by_lesson[1].time_slot_id == 200
    assert assignment_by_lesson[1].room_id == 500


# --- Fixed slot conflicts are reported as ordinary, clearly-explained
# scheduling failures, not silently dropped or misattributed. ---


def test_greedy_reports_clear_failure_when_fixed_time_slots_collide() -> None:
    """Two lessons for the SAME class, both fixed to the SAME time slot --
    an unconditional H2 (class conflict) no matter which teacher/room is
    tried for either. Greedy must report a real, specific violation for
    the failing lesson, not an empty/generic "no candidate" message."""
    lesson_a = _lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=10, fixed_time_slot_id=100)
    lesson_b = _lesson(2, class_subject_requirement_id=2, class_id=1, subject_id=20, fixed_time_slot_id=100)

    resources = _empty_resources(
        time_slot_ids=[100, 200],
        teacher_qualifications=[
            TeacherQualification(teacher_id=10, subject_id=10),
            TeacherQualification(teacher_id=20, subject_id=20),
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

    result = schedule_greedy([lesson_a, lesson_b], resources)

    assert result.success is False
    assert len(result.lesson_failures) == 1
    failure = result.lesson_failures[0]
    assert failure.lesson_id == 2  # whichever is processed second
    assert len(failure.reasons) >= 1
    assert all(reason.type == "H2_CLASS_CONFLICT" for reason in failure.reasons)
    assert all(reason.time_slot_id == 100 for reason in failure.reasons)


def test_backtracking_reports_infeasible_when_fixed_time_slots_collide() -> None:
    """Same unavoidable collision as above. Backtracking correctly reports
    failure (never silently succeeds or returns a partial result) -- but
    per its existing, pre-Task-28 design (see backtracking.py's module
    docstring), a failure reached by fully exhausting the search space
    reports failure_type only, not a per-lesson lesson_failures list, since
    which combination doesn't work is an emergent property of the whole
    search tree here (both lessons' teacher/room choices are still free;
    only their time is pinned). This is the same limitation that already
    applies to any other genuinely combinatorial infeasibility -- not a
    Task 28 regression.
    """
    lesson_a = _lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=10, fixed_time_slot_id=100)
    lesson_b = _lesson(2, class_subject_requirement_id=2, class_id=1, subject_id=20, fixed_time_slot_id=100)

    resources = _empty_resources(
        time_slot_ids=[100, 200],
        teacher_qualifications=[
            TeacherQualification(teacher_id=10, subject_id=10),
            TeacherQualification(teacher_id=20, subject_id=20),
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

    result = schedule_backtracking([lesson_a, lesson_b], resources)

    assert result.success is False
    assert result.state is None
    assert result.failure_type == "DEFINITELY_INFEASIBLE"
