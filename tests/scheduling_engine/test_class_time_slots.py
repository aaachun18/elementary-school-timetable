"""Task 98: H13 -- a class may only be scheduled in the time slots its
grade is open for in the semester (ClassAllowedTimeSlots). Pure Python, no
database."""

from dataclasses import replace

import pytest

from scheduling_engine.algorithms.backtracking import schedule_backtracking
from scheduling_engine.algorithms.blocks import SchedulingUnit, unit_windows
from scheduling_engine.algorithms.greedy import schedule_greedy
from scheduling_engine.algorithms.resources import SchedulingResources, candidate_time_slot_ids
from scheduling_engine.models.domain import (
    ClassAllowedTimeSlots,
    LessonAssignment,
    LessonBlock,
    RequirementPeriods,
    TimeSlotInfo,
    TimeSlotPosition,
)
from scheduling_engine.static_feasibility import check_static_feasibility

# Monday periods 1-4 (slots 1-4), Tuesday periods 1-4 (slots 5-8).
SLOTS = {slot_id: (1 + (slot_id - 1) // 4, 1 + (slot_id - 1) % 4) for slot_id in range(1, 9)}
# Class 1 (a 低年級 class, say) is open on Monday periods 1-2 and all of Tuesday.
OPEN_FOR_CLASS_1 = frozenset({1, 2, 5, 6, 7, 8})


def _lesson(lesson_id: int, requirement_id: int, class_id: int) -> LessonAssignment:
    return LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=requirement_id,
        class_id=class_id,
        subject_id=10,
        teacher_id=None,
        time_slot_id=None,
        room_id=None,
    )


def _resources(lessons: list[LessonAssignment], **overrides: object) -> SchedulingResources:
    periods: dict[int, int] = {}
    for lesson in lessons:
        periods[lesson.class_subject_requirement_id] = periods.get(lesson.class_subject_requirement_id, 0) + 1
    base: dict[str, object] = dict(
        time_slot_ids=list(SLOTS),
        teacher_ids=[1, 2],
        teacher_unavailability=[],
        required_teacher_rules=[],
        required_room_rules=[],
        time_slots=[TimeSlotInfo(time_slot_id=slot_id, is_teaching_period=True) for slot_id in SLOTS],
        active_statuses=[],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=r, weekly_periods=n) for r, n in periods.items()
        ],
        teacher_workload_limits=[],
        time_slot_positions=[
            TimeSlotPosition(time_slot_id=slot_id, weekday=weekday, period=period)
            for slot_id, (weekday, period) in SLOTS.items()
        ],
        class_allowed_time_slots=[ClassAllowedTimeSlots(class_id=1, time_slot_ids=OPEN_FOR_CLASS_1)],
    )
    base.update(overrides)
    return SchedulingResources(**base)  # type: ignore[arg-type]


def test_candidate_slots_are_the_open_ones_for_a_restricted_class() -> None:
    lessons = [_lesson(1, 1, class_id=1), _lesson(2, 2, class_id=2)]
    resources = _resources(lessons)

    assert candidate_time_slot_ids(lessons[0], resources) == [1, 2, 5, 6, 7, 8]
    assert candidate_time_slot_ids(lessons[1], resources) == list(SLOTS)  # unrestricted


def test_fixed_slot_stays_the_only_candidate_even_if_closed() -> None:
    """The fixed slot is never silently dropped: H13 and the pre-check
    report a closed one instead."""
    lesson = replace(_lesson(1, 1, class_id=1), time_slot_id=3)

    assert candidate_time_slot_ids(lesson, _resources([lesson])) == [3]


@pytest.mark.parametrize("algorithm", ["greedy", "backtracking"])
def test_both_algorithms_keep_a_class_inside_its_open_slots(algorithm: str) -> None:
    lessons = [_lesson(i, 1, class_id=1) for i in range(1, 7)] + [_lesson(7, 2, class_id=2)]
    resources = _resources(lessons)

    run = schedule_greedy if algorithm == "greedy" else schedule_backtracking
    result = run(lessons, resources)

    assert result.success is True
    assert result.state is not None
    class_1_slots = {a.time_slot_id for a in result.state.assignments if a.class_id == 1}
    assert class_1_slots == set(OPEN_FOR_CLASS_1)


def test_block_windows_lie_entirely_inside_the_open_slots() -> None:
    lessons = [_lesson(1, 1, class_id=1), _lesson(2, 1, class_id=1)]
    block = LessonBlock(class_subject_requirement_id=1, block_no=1, lesson_ids=(1, 2))
    resources = _resources(lessons, lesson_blocks=[block])

    windows = unit_windows(SchedulingUnit(tuple(lessons), block), resources)

    # Monday 2-3 would cross into the closed period 3.
    assert windows == [(1, 2), (5, 6), (6, 7), (7, 8)]


def test_more_lessons_than_open_slots_is_a_pre_check_failure() -> None:
    lessons = [_lesson(i, 1, class_id=1) for i in range(1, 8)]

    violations = check_static_feasibility(lessons, _resources(lessons)).violations

    assert [(v.type, v.class_id) for v in violations] == [("STATIC_CLASS_SLOTS_INSUFFICIENT", 1)]
    assert "7 堂課" in violations[0].message and "6 個可排節次" in violations[0].message


def test_lesson_fixed_to_a_closed_slot_is_a_pre_check_failure() -> None:
    lessons = [replace(_lesson(1, 1, class_id=1), time_slot_id=3)]

    violations = check_static_feasibility(lessons, _resources(lessons)).violations

    assert [(v.type, v.lesson_id, v.time_slot_id) for v in violations] == [
        ("STATIC_FIXED_SLOT_CLASS_CLOSED", 1, 3)
    ]


def test_unrestricted_classes_pass_the_pre_checks() -> None:
    lessons = [_lesson(i, 1, class_id=2) for i in range(1, 9)]

    assert check_static_feasibility(lessons, _resources(lessons)).feasible
