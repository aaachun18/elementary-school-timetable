"""Tests for the soft constraint 「國語文、數學排在第 1–2 節」
(scheduling_engine/algorithms/preferred_periods.py). Pure Python, no
database: a legal timetable goes in, a legal timetable with more preferred
lessons in the first two teaching periods comes out."""

from dataclasses import replace

from scheduling_engine.algorithms.blocks import block_constraints
from scheduling_engine.algorithms.preferred_periods import (
    optimize_preferred_periods,
    preferred_time_slot_ids,
)
from scheduling_engine.algorithms.resources import (
    SchedulingResources,
    build_real_time_constraints,
)
from scheduling_engine.models.domain import (
    LessonAssignment,
    LessonBlock,
    RequirementPeriods,
    TeacherUnavailability,
    TimeSlotInfo,
    TimeSlotPosition,
)

MATH = 1
ART = 9
MATH_REQUIREMENT = 100
ART_REQUIREMENT = 900
CLASS_ID = 1
MATH_TEACHER = 7
ART_TEACHER = 8


def _slot_id(weekday: int, period: int) -> int:
    return weekday * 10 + period


def _resources(weekdays: tuple[int, ...] = (1,), **overrides: object) -> SchedulingResources:
    """Periods 0 (早自習, not teaching) to 4 on each weekday."""
    positions = [
        TimeSlotPosition(_slot_id(day, period), day, period)
        for day in weekdays
        for period in range(5)
    ]
    base: dict[str, object] = dict(
        time_slot_ids=[position.time_slot_id for position in positions],
        teacher_ids=[MATH_TEACHER, ART_TEACHER],
        teacher_unavailability=[],
        required_teacher_rules=[],
        required_room_rules=[],
        time_slots=[
            TimeSlotInfo(position.time_slot_id, is_teaching_period=position.period != 0)
            for position in positions
        ],
        active_statuses=[],
        requirement_periods=[],
        teacher_workload_limits=[],
        time_slot_positions=positions,
    )
    base.update(overrides)
    return SchedulingResources(**base)  # type: ignore[arg-type]


def _lesson(
    lesson_id: int, subject_id: int, *, slot: int | None = None, fixed: bool = False
) -> tuple[LessonAssignment, LessonAssignment]:
    """(the pending lesson the search got, its placed assignment)."""
    requirement_id = MATH_REQUIREMENT if subject_id == MATH else ART_REQUIREMENT
    teacher_id = MATH_TEACHER if subject_id == MATH else ART_TEACHER
    pending = LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=requirement_id,
        class_id=CLASS_ID,
        subject_id=subject_id,
        teacher_id=None,
        time_slot_id=slot if fixed else None,
        room_id=None,
    )
    return pending, replace(pending, teacher_id=teacher_id, time_slot_id=slot)


def _split(
    lessons: list[tuple[LessonAssignment, LessonAssignment]],
) -> tuple[list[LessonAssignment], list[LessonAssignment]]:
    return [pending for pending, _ in lessons], [placed for _, placed in lessons]


def _slots_of(assignments: list[LessonAssignment], subject_id: int) -> list[int | None]:
    return sorted(
        (a.time_slot_id for a in assignments if a.subject_id == subject_id),
        key=lambda slot: slot or 0,
    )


def _assert_legal(assignments: list[LessonAssignment], resources: SchedulingResources) -> None:
    constraints = [
        *build_real_time_constraints(resources, include_teacher_workload=True),
        *block_constraints(resources),
    ]
    for constraint in constraints:
        assert constraint.validate(assignments), constraint.explain_violations(assignments)


def test_preferred_slots_are_each_days_first_two_teaching_periods() -> None:
    resources = _resources(weekdays=(1, 2))

    assert preferred_time_slot_ids(resources) == {
        _slot_id(1, 1),
        _slot_id(1, 2),
        _slot_id(2, 1),
        _slot_id(2, 2),
    }


def test_math_trades_places_with_art_into_periods_1_and_2() -> None:
    pending, placed = _split(
        [
            _lesson(1, ART, slot=_slot_id(1, 1)),
            _lesson(2, ART, slot=_slot_id(1, 2)),
            _lesson(3, MATH, slot=_slot_id(1, 3)),
            _lesson(4, MATH, slot=_slot_id(1, 4)),
        ]
    )
    resources = _resources()

    result = optimize_preferred_periods(placed, pending, resources, frozenset({MATH}))

    assert result.score_before == 0
    assert result.score_after == 2
    assert result.preferred_lesson_count == 2
    assert _slots_of(result.assignments, MATH) == [_slot_id(1, 1), _slot_id(1, 2)]
    assert _slots_of(result.assignments, ART) == [_slot_id(1, 3), _slot_id(1, 4)]
    # Teachers never change, only time slots.
    assert {a.lesson_id: a.teacher_id for a in result.assignments} == {
        a.lesson_id: a.teacher_id for a in placed
    }
    _assert_legal(result.assignments, resources)


def test_a_hard_constraint_is_never_broken_for_the_preference() -> None:
    pending, placed = _split(
        [
            _lesson(1, ART, slot=_slot_id(1, 1)),
            _lesson(2, ART, slot=_slot_id(1, 2)),
            _lesson(3, MATH, slot=_slot_id(1, 3)),
            _lesson(4, MATH, slot=_slot_id(1, 4)),
        ]
    )
    # H4: the math teacher can't teach period 1.
    resources = _resources(
        teacher_unavailability=[TeacherUnavailability(MATH_TEACHER, _slot_id(1, 1))]
    )

    result = optimize_preferred_periods(placed, pending, resources, frozenset({MATH}))

    assert result.score_after == 1
    assert _slot_id(1, 1) not in _slots_of(result.assignments, MATH)
    _assert_legal(result.assignments, resources)


def test_a_fixed_lesson_never_moves() -> None:
    pending, placed = _split(
        [
            _lesson(1, ART, slot=_slot_id(1, 1)),
            _lesson(2, ART, slot=_slot_id(1, 2)),
            _lesson(3, MATH, slot=_slot_id(1, 3)),
            _lesson(4, MATH, slot=_slot_id(1, 4), fixed=True),
        ]
    )
    resources = _resources()

    result = optimize_preferred_periods(placed, pending, resources, frozenset({MATH}))

    by_id = {a.lesson_id: a for a in result.assignments}
    assert by_id[4].time_slot_id == _slot_id(1, 4)
    assert result.score_after == 1


def test_a_math_block_moves_as_one_into_periods_1_and_2() -> None:
    pending, placed = _split(
        [
            _lesson(1, ART, slot=_slot_id(1, 1)),
            _lesson(2, ART, slot=_slot_id(1, 2)),
            _lesson(3, MATH, slot=_slot_id(1, 3)),
            _lesson(4, MATH, slot=_slot_id(1, 4)),
        ]
    )
    resources = _resources(
        lesson_blocks=[LessonBlock(MATH_REQUIREMENT, block_no=1, lesson_ids=(3, 4))],
        requirement_periods=[RequirementPeriods(MATH_REQUIREMENT, 2)],
    )

    result = optimize_preferred_periods(placed, pending, resources, frozenset({MATH}))

    by_id = {a.lesson_id: a for a in result.assignments}
    assert (by_id[3].time_slot_id, by_id[4].time_slot_id) == (_slot_id(1, 1), _slot_id(1, 2))
    _assert_legal(result.assignments, resources)


def test_separate_lessons_are_not_piled_onto_one_day() -> None:
    """Two separate math lessons on two days stay one a day: only day 1
    has free morning periods, so only one of them can come forward."""
    pending, placed = _split(
        [
            _lesson(1, MATH, slot=_slot_id(1, 3)),
            _lesson(2, MATH, slot=_slot_id(2, 3)),
            _lesson(3, ART, slot=_slot_id(2, 1), fixed=True),
            _lesson(4, ART, slot=_slot_id(2, 2), fixed=True),
        ]
    )
    resources = _resources(weekdays=(1, 2))

    result = optimize_preferred_periods(placed, pending, resources, frozenset({MATH}))

    assert result.score_after == 1
    math_days = sorted((a.time_slot_id or 0) // 10 for a in result.assignments if a.subject_id == MATH)
    assert math_days == [1, 2]


def test_same_input_gives_the_same_timetable() -> None:
    lessons = [
        _lesson(1, ART, slot=_slot_id(1, 1)),
        _lesson(2, MATH, slot=_slot_id(1, 3)),
        _lesson(3, ART, slot=_slot_id(2, 2)),
        _lesson(4, MATH, slot=_slot_id(2, 4)),
    ]
    pending, placed = _split(lessons)
    resources = _resources(weekdays=(1, 2))

    first = optimize_preferred_periods(placed, pending, resources, frozenset({MATH}))
    second = optimize_preferred_periods(placed, pending, resources, frozenset({MATH}))

    assert first.assignments == second.assignments
    assert first.score_after == 2


def test_nothing_to_prefer_leaves_the_timetable_alone() -> None:
    pending, placed = _split([_lesson(1, ART, slot=_slot_id(1, 3))])

    result = optimize_preferred_periods(placed, pending, _resources(), frozenset({MATH}))

    assert result.assignments == placed
    assert result.steps_taken == 0
