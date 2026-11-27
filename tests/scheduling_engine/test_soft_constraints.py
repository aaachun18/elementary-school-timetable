"""Tests for the soft constraints S9 (體育 not in 第 1、4、5 節) and S10
(活動性課程 in the last period of a full day), scheduling_engine/algorithms/
preferred_periods.py. Pure Python, no database."""

from dataclasses import replace

from scheduling_engine.algorithms.blocks import block_constraints
from scheduling_engine.algorithms.preferred_periods import (
    avoided_time_slot_ids,
    last_time_slot_ids_by_class,
    optimize_preferred_periods,
)
from scheduling_engine.algorithms.resources import SchedulingResources, build_real_time_constraints
from scheduling_engine.models.domain import (
    ClassAllowedTimeSlots,
    LessonAssignment,
    TimeSlotInfo,
    TimeSlotPosition,
)

PE = 1
ART = 2
MATH = 3
CLASS_ID = 1
# Periods 0 (早自習) and 5 (午休) are not teaching periods: 第 1–4 節 are
# periods 1–4, 第 5 節 is period 6, 第 6 節 period 7.
PERIODS = range(8)
NON_TEACHING = (0, 5)


def _slot_id(weekday: int, period: int) -> int:
    return weekday * 10 + period


def _resources(weekdays: tuple[int, ...] = (1,), **overrides: object) -> SchedulingResources:
    positions = [TimeSlotPosition(_slot_id(day, period), day, period) for day in weekdays for period in PERIODS]
    base: dict[str, object] = dict(
        time_slot_ids=[position.time_slot_id for position in positions],
        teacher_ids=[7, 8, 9],
        teacher_unavailability=[],
        required_teacher_rules=[],
        required_room_rules=[],
        time_slots=[
            TimeSlotInfo(position.time_slot_id, is_teaching_period=position.period not in NON_TEACHING)
            for position in positions
        ],
        active_statuses=[],
        requirement_periods=[],
        teacher_workload_limits=[],
        time_slot_positions=positions,
    )
    base.update(overrides)
    return SchedulingResources(**base)  # type: ignore[arg-type]


def _lesson(lesson_id: int, subject_id: int, slot: int) -> tuple[LessonAssignment, LessonAssignment]:
    """(the pending lesson the search got, its placed assignment); one
    requirement and one teacher per subject."""
    pending = LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=subject_id * 100,
        class_id=CLASS_ID,
        subject_id=subject_id,
        teacher_id=None,
        time_slot_id=None,
        room_id=None,
    )
    return pending, replace(pending, teacher_id=6 + subject_id, time_slot_id=slot)


def _split(
    lessons: list[tuple[LessonAssignment, LessonAssignment]],
) -> tuple[list[LessonAssignment], list[LessonAssignment]]:
    return [pending for pending, _ in lessons], [placed for _, placed in lessons]


def _slot_of(assignments: list[LessonAssignment], lesson_id: int) -> int | None:
    return next(a.time_slot_id for a in assignments if a.lesson_id == lesson_id)


def _assert_legal(assignments: list[LessonAssignment], resources: SchedulingResources) -> None:
    for constraint in [
        *build_real_time_constraints(resources, include_teacher_workload=True),
        *block_constraints(resources),
    ]:
        assert constraint.validate(assignments), constraint.explain_violations(assignments)


def test_avoided_slots_are_the_1st_4th_and_5th_teaching_periods() -> None:
    # 第 5 節 is the first period after 午休 (period 6), not period 5.
    assert avoided_time_slot_ids(_resources()) == {_slot_id(1, 1), _slot_id(1, 4), _slot_id(1, 6)}


def test_pe_leaves_the_first_period() -> None:
    pending, placed = _split([_lesson(1, PE, _slot_id(1, 1)), _lesson(2, ART, _slot_id(1, 2))])
    resources = _resources()

    result = optimize_preferred_periods(
        placed, pending, resources, frozenset(), avoided_subject_ids=frozenset({PE})
    )

    assert _slot_of(result.assignments, 1) not in avoided_time_slot_ids(resources)
    assert result.avoided_in_place == 0
    assert result.score_before == -1
    assert result.score_after == 0
    _assert_legal(result.assignments, resources)


def test_last_period_only_on_full_days() -> None:
    # Monday is open all day for the class; Tuesday only until 午休.
    morning_only = {_slot_id(2, period) for period in (1, 2, 3, 4)}
    full_day = {_slot_id(1, period) for period in (1, 2, 3, 4, 6, 7)}
    resources = _resources(
        weekdays=(1, 2),
        class_allowed_time_slots=[ClassAllowedTimeSlots(CLASS_ID, frozenset(full_day | morning_only))],
    )

    assert last_time_slot_ids_by_class({CLASS_ID}, resources) == {CLASS_ID: frozenset({_slot_id(1, 7)})}


def test_an_activity_subject_takes_the_last_period_of_a_full_day() -> None:
    pending, placed = _split([_lesson(1, ART, _slot_id(1, 2)), _lesson(2, MATH, _slot_id(1, 7))])
    resources = _resources()

    result = optimize_preferred_periods(
        placed, pending, resources, frozenset(), activity_subject_ids=frozenset({ART})
    )

    assert _slot_of(result.assignments, 1) == _slot_id(1, 7)
    assert _slot_of(result.assignments, 2) == _slot_id(1, 2)
    assert result.activity_in_last_periods == 1
    assert result.last_period_count == 1
    _assert_legal(result.assignments, resources)


def test_one_preference_is_not_bought_with_another() -> None:
    # 體育 is an activity subject too, and the class's day ends at 第 5 節
    # -- an avoided period: moving 體育 there would gain a point (S10) only
    # to lose one (S9), so nothing moves.
    resources = _resources(
        class_allowed_time_slots=[
            ClassAllowedTimeSlots(CLASS_ID, frozenset(_slot_id(1, period) for period in (1, 2, 3, 4, 6)))
        ]
    )
    pending, placed = _split([_lesson(1, PE, _slot_id(1, 2)), _lesson(2, MATH, _slot_id(1, 6))])

    result = optimize_preferred_periods(
        placed,
        pending,
        resources,
        frozenset(),
        avoided_subject_ids=frozenset({PE}),
        activity_subject_ids=frozenset({PE}),
    )

    assert result.assignments == placed
    assert result.steps_taken == 0
