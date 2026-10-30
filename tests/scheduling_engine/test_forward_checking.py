"""Tests for the Forward Checking Scheduler (Task 104,
scheduling_engine/algorithms/forward_checking.py). Pure Python, no
database. Every successful timetable is also checked against the hard
constraint classes themselves (_assert_valid)."""

import json
from pathlib import Path

from scheduling_engine.algorithms.backtracking import schedule_backtracking
from scheduling_engine.algorithms.blocks import block_constraints
from scheduling_engine.algorithms.forward_checking import (
    ForwardCheckingResult,
    luby,
    schedule_forward_checking,
)
from scheduling_engine.algorithms.resources import SchedulingResources, build_real_time_constraints
from scheduling_engine.constraints.weekly_periods import WeeklyPeriodsConstraint
from scheduling_engine.models.domain import (
    ActiveStatusInfo,
    ClassAllowedTimeSlots,
    CombinedLesson,
    DefaultRoom,
    LessonAssignment,
    LessonBlock,
    RequiredRoomRule,
    RequiredTeacherRule,
    RequirementPeriods,
    RoomCapacity,
    TeacherUnavailability,
    TeacherWorkloadLimit,
    TimeSlotInfo,
    TimeSlotPosition,
)

WEEKDAYS = (1, 2, 3, 4, 5)


def _slot(weekday: int, period: int) -> int:
    """Time slot id of a weekday (1 = Monday) and period: 23 = Tuesday 3."""
    return weekday * 10 + period


def _lesson(
    lesson_id: int, requirement_id: int, class_id: int = 1, fixed_slot: int | None = None
) -> LessonAssignment:
    return LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=requirement_id,
        class_id=class_id,
        subject_id=requirement_id,
        teacher_id=None,
        time_slot_id=fixed_slot,
        room_id=None,
    )


def _resources(
    lessons: list[LessonAssignment],
    periods_by_day: dict[int, list[int]],
    teacher_ids: list[int],
    **overrides: object,
) -> SchedulingResources:
    """Teaching periods per weekday; every requirement's weekly periods are
    its number of lessons."""
    slots = [_slot(day, period) for day, periods in periods_by_day.items() for period in periods]
    counts: dict[int, int] = {}
    for lesson in lessons:
        counts[lesson.class_subject_requirement_id] = counts.get(lesson.class_subject_requirement_id, 0) + 1
    base: dict[str, object] = dict(
        time_slot_ids=slots,
        teacher_ids=teacher_ids,
        teacher_unavailability=[],
        required_teacher_rules=[],
        required_room_rules=[],
        time_slots=[TimeSlotInfo(time_slot_id=slot, is_teaching_period=True) for slot in slots],
        active_statuses=[],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=requirement, weekly_periods=count)
            for requirement, count in counts.items()
        ],
        teacher_workload_limits=[],
        time_slot_positions=[
            TimeSlotPosition(time_slot_id=_slot(day, period), weekday=day, period=period)
            for day, periods in periods_by_day.items()
            for period in periods
        ],
    )
    base.update(overrides)
    return SchedulingResources(**base)  # type: ignore[arg-type]


def _assert_valid(
    result: ForwardCheckingResult, lessons: list[LessonAssignment], resources: SchedulingResources
) -> dict[int, LessonAssignment]:
    assert result.success is True
    assert result.failure_type is None
    assert result.state is not None
    assignments = result.state.assignments
    assert sorted(a.lesson_id for a in assignments) == sorted(lesson.lesson_id for lesson in lessons)
    constraints = [
        *build_real_time_constraints(resources, include_teacher_workload=True),
        *block_constraints(resources),
        WeeklyPeriodsConstraint(resources.requirement_periods),
    ]
    for constraint in constraints:
        assert constraint.explain_violations(assignments) == []
    return {assignment.lesson_id: assignment for assignment in assignments}


def _required_teachers(pairs: dict[int, int]) -> list[RequiredTeacherRule]:
    return [
        RequiredTeacherRule(class_subject_requirement_id=requirement, required_teacher_id=teacher)
        for requirement, teacher in pairs.items()
    ]


# --- Success and the hard constraints ---


def test_places_every_lesson_with_ample_resources() -> None:
    lessons = [_lesson(1, 1), _lesson(2, 2)]
    resources = _resources(lessons, {1: [1, 2]}, [7])

    result = schedule_forward_checking(lessons, resources)

    _assert_valid(result, lessons, resources)
    assert result.node_count >= 2


def test_no_lessons_is_an_empty_timetable() -> None:
    result = schedule_forward_checking([], _resources([], {1: [1]}, [7]))

    assert result.success is True
    assert result.state is not None
    assert result.state.assignments == []


def test_one_teacher_never_teaches_two_lessons_at_once() -> None:
    # H1: two classes, one teacher, two periods.
    lessons = [_lesson(1, 1, class_id=1), _lesson(2, 2, class_id=2)]
    resources = _resources(
        lessons, {1: [1, 2]}, [7], required_teacher_rules=_required_teachers({1: 7, 2: 7})
    )

    placed = _assert_valid(schedule_forward_checking(lessons, resources), lessons, resources)

    assert placed[1].time_slot_id != placed[2].time_slot_id


def test_one_class_never_has_two_lessons_at_once() -> None:
    # H2: a class with as many lessons as periods fills every period.
    lessons = [_lesson(1, 1), _lesson(2, 2), _lesson(3, 3)]
    resources = _resources(lessons, {1: [1, 2, 3]}, [7, 8, 9])

    placed = _assert_valid(schedule_forward_checking(lessons, resources), lessons, resources)

    assert {a.time_slot_id for a in placed.values()} == {11, 12, 13}


def test_a_room_holds_one_lesson_unless_its_capacity_is_larger() -> None:
    # H3: two classes need room 50 in the only period there is.
    lessons = [_lesson(1, 1, class_id=1), _lesson(2, 2, class_id=2)]
    rooms = [
        RequiredRoomRule(class_subject_requirement_id=1, room_id=50),
        RequiredRoomRule(class_subject_requirement_id=2, room_id=50),
    ]
    single = _resources(lessons, {1: [1]}, [7, 8], required_room_rules=rooms)
    shared = _resources(
        lessons,
        {1: [1]},
        [7, 8],
        required_room_rules=rooms,
        room_capacities=[RoomCapacity(room_id=50, max_classes=2)],
    )

    assert schedule_forward_checking(lessons, single).failure_type == "DEFINITELY_INFEASIBLE"
    placed = _assert_valid(schedule_forward_checking(lessons, shared), lessons, shared)
    assert placed[1].room_id == placed[2].room_id == 50


def test_respects_teacher_unavailability() -> None:
    # H4: teacher 7 can only teach Monday 2.
    lessons = [_lesson(1, 1)]
    resources = _resources(
        lessons,
        {1: [1, 2, 3]},
        [7],
        required_teacher_rules=_required_teachers({1: 7}),
        teacher_unavailability=[
            TeacherUnavailability(teacher_id=7, time_slot_id=11),
            TeacherUnavailability(teacher_id=7, time_slot_id=13),
        ],
    )

    placed = _assert_valid(schedule_forward_checking(lessons, resources), lessons, resources)

    assert placed[1].time_slot_id == 12
    assert placed[1].teacher_id == 7


def test_respects_teacher_maximum_workload() -> None:
    # H8: three lessons for a teacher allowed two periods a week.
    lessons = [_lesson(1, 1, class_id=1), _lesson(2, 2, class_id=2), _lesson(3, 3, class_id=3)]
    resources = _resources(
        lessons,
        {1: [1, 2, 3]},
        [7],
        required_teacher_rules=_required_teachers({1: 7, 2: 7, 3: 7}),
        teacher_workload_limits=[TeacherWorkloadLimit(teacher_id=7, max_weekly_periods=2)],
    )

    result = schedule_forward_checking(lessons, resources)

    assert result.success is False
    assert result.failure_type == "DEFINITELY_INFEASIBLE"
    assert result.state is None


def test_respects_the_time_slots_a_class_may_use() -> None:
    # H13: class 1 may only use Monday 3.
    lessons = [_lesson(1, 1)]
    resources = _resources(
        lessons,
        {1: [1, 2, 3]},
        [7],
        class_allowed_time_slots=[ClassAllowedTimeSlots(class_id=1, time_slot_ids=frozenset({13}))],
    )

    placed = _assert_valid(schedule_forward_checking(lessons, resources), lessons, resources)

    assert placed[1].time_slot_id == 13


def test_a_fixed_lesson_stays_in_its_fixed_slot() -> None:
    lessons = [_lesson(1, 1, fixed_slot=12), _lesson(2, 2)]
    resources = _resources(lessons, {1: [1, 2]}, [7])

    placed = _assert_valid(schedule_forward_checking(lessons, resources), lessons, resources)

    assert placed[1].time_slot_id == 12
    assert placed[2].time_slot_id == 11


def test_blocks_are_consecutive_and_on_different_days() -> None:
    # 連堂 2+1: the pair in adjacent periods of one day, the single on another.
    lessons = [_lesson(1, 1), _lesson(2, 1), _lesson(3, 1)]
    resources = _resources(
        lessons,
        {1: [1, 2], 2: [1, 2]},
        [7],
        lesson_blocks=[
            LessonBlock(class_subject_requirement_id=1, block_no=1, lesson_ids=(1, 2)),
            LessonBlock(class_subject_requirement_id=1, block_no=2, lesson_ids=(3,)),
        ],
    )

    placed = _assert_valid(schedule_forward_checking(lessons, resources), lessons, resources)

    pair_day = placed[1].time_slot_id // 10
    assert placed[2].time_slot_id == placed[1].time_slot_id + 1
    assert placed[3].time_slot_id // 10 != pair_day


def test_two_blocks_of_one_requirement_cannot_share_the_only_day() -> None:
    lessons = [_lesson(1, 1), _lesson(2, 1)]
    resources = _resources(
        lessons,
        {1: [1, 2, 3]},
        [7],
        lesson_blocks=[
            LessonBlock(class_subject_requirement_id=1, block_no=1, lesson_ids=(1,)),
            LessonBlock(class_subject_requirement_id=1, block_no=2, lesson_ids=(2,)),
        ],
    )

    assert schedule_forward_checking(lessons, resources).failure_type == "DEFINITELY_INFEASIBLE"


def test_a_combined_lesson_is_one_period_for_its_teacher() -> None:
    # 共同排課: classes 1 and 2 together with teacher 7, who may teach only
    # one period a week -- possible only because it counts once.
    lessons = [_lesson(1, 1, class_id=1), _lesson(2, 2, class_id=2)]
    resources = _resources(
        lessons,
        {1: [1, 2]},
        [7],
        required_teacher_rules=_required_teachers({1: 7, 2: 7}),
        teacher_workload_limits=[TeacherWorkloadLimit(teacher_id=7, max_weekly_periods=1)],
        combined_lessons=[
            CombinedLesson(key="1:1", member_lesson_ids=((1,), (2,)), room_id=60, teacher_ids=(7,))
        ],
    )

    placed = _assert_valid(schedule_forward_checking(lessons, resources), lessons, resources)

    assert placed[1].time_slot_id == placed[2].time_slot_id
    assert placed[1].room_id == placed[2].room_id == 60


# --- Failures ---


def test_reports_definitely_infeasible_when_lessons_outnumber_slots() -> None:
    lessons = [_lesson(1, 1), _lesson(2, 2), _lesson(3, 3)]
    resources = _resources(lessons, {1: [1, 2]}, [7, 8, 9])

    result = schedule_forward_checking(lessons, resources)

    assert result.success is False
    assert result.state is None
    assert result.failure_type == "DEFINITELY_INFEASIBLE"
    assert result.lesson_failures == []


def test_reports_a_lesson_nobody_may_teach_before_searching() -> None:
    # The required teacher takes no part in the semester.
    lessons = [_lesson(1, 1)]
    resources = _resources(lessons, {1: [1]}, [7], required_teacher_rules=_required_teachers({1: 99}))

    result = schedule_forward_checking(lessons, resources)

    assert result.failure_type == "DEFINITELY_INFEASIBLE"
    assert [failure.lesson_id for failure in result.lesson_failures] == [1]
    assert result.node_count == 0


def test_reports_h7_mismatch_when_a_requirement_is_short_of_lessons() -> None:
    lessons = [_lesson(1, 1)]
    resources = _resources(
        lessons,
        {1: [1, 2]},
        [7],
        requirement_periods=[RequirementPeriods(class_subject_requirement_id=1, weekly_periods=2)],
    )

    result = schedule_forward_checking(lessons, resources)

    assert result.success is False
    assert result.failure_type is None
    assert result.state is None
    assert [v.type for v in result.post_hoc_violations] == [WeeklyPeriodsConstraint.VIOLATION_TYPE]


def test_stops_at_the_node_limit_without_claiming_infeasibility() -> None:
    lessons, resources = _full_week_class()

    result = schedule_forward_checking(lessons, resources, max_nodes=3)

    assert result.success is False
    assert result.state is None
    assert result.failure_type == "SEARCH_LIMIT_EXCEEDED"
    assert result.node_count == 3


def test_stops_at_the_time_limit_without_claiming_infeasibility() -> None:
    lessons, resources = _full_week_class()

    result = schedule_forward_checking(lessons, resources, timeout_seconds=0)

    assert result.success is False
    assert result.state is None
    assert result.failure_type == "TIMEOUT"


# --- Seeds ---


def test_same_seed_same_timetable() -> None:
    lessons, resources = _full_week_class()

    first = schedule_forward_checking(lessons, resources, seed=42)
    second = schedule_forward_checking(lessons, resources, seed=42)

    assert first.state is not None and second.state is not None
    assert sorted(first.state.assignments, key=lambda a: a.lesson_id) == sorted(
        second.state.assignments, key=lambda a: a.lesson_id
    )
    assert first.seed == second.seed == 42


def test_different_seeds_give_different_timetables() -> None:
    lessons, resources = _full_week_class()

    timetables = set()
    for seed in range(5):
        result = schedule_forward_checking(lessons, resources, seed=seed)
        placed = _assert_valid(result, lessons, resources)
        timetables.add(tuple(sorted((lesson_id, a.time_slot_id) for lesson_id, a in placed.items())))

    assert len(timetables) > 1


def test_luby_sequence() -> None:
    assert [luby(index) for index in range(1, 16)] == [1, 1, 2, 1, 1, 2, 4, 1, 1, 2, 1, 1, 2, 4, 8]


# --- A class that fills every slot ---


def _full_week_class() -> tuple[list[LessonAssignment], SchedulingResources]:
    """Modelled on a real 二年甲班: 23 lessons in exactly 23 time slots --
    Monday, Wednesday to Friday periods 1-4, Tuesday 1-4 and 6-8 -- with
    連堂 patterns, fixed slots and part-time teachers."""
    homeroom, local_language, life, sports, music = 1, 2, 3, 4, 5
    periods = {1: [1, 2, 3, 4], 2: [1, 2, 3, 4, 6, 7, 8], 3: [1, 2, 3, 4], 4: [1, 2, 3, 4], 5: [1, 2, 3, 4]}
    # requirement: (lessons, pattern, teacher, room, fixed slots)
    requirements: dict[int, tuple[int, list[int], int, int | None, list[int]]] = {
        1: (6, [2, 1, 1, 1, 1], homeroom, None, []),  # 國語文
        2: (1, [], local_language, None, []),  # 本土語文
        3: (4, [1, 1, 1, 1], homeroom, None, []),  # 數學
        4: (3, [2, 1], life, None, []),  # 生活課程
        5: (1, [], homeroom, None, []),  # 健康
        6: (2, [1, 1], sports, 50, []),  # 體育
        7: (2, [2], life, 40, [_slot(2, 1), _slot(2, 2)]),  # 美勞
        8: (1, [], homeroom, None, [_slot(3, 3)]),  # 地球公民
        9: (1, [], homeroom, None, [_slot(3, 4)]),  # 藝起發光
        10: (1, [], homeroom, None, []),  # 國際視野
        11: (1, [], music, 20, []),  # 音樂
    }
    lessons: list[LessonAssignment] = []
    blocks: list[LessonBlock] = []
    next_id = 1
    for requirement, (count, pattern, _, _, fixed) in requirements.items():
        ids = list(range(next_id, next_id + count))
        next_id += count
        for index, lesson_id in enumerate(ids):
            lessons.append(_lesson(lesson_id, requirement, fixed_slot=fixed[index] if fixed else None))
        start = 0
        for block_no, size in enumerate(pattern, start=1):
            blocks.append(LessonBlock(requirement, block_no, tuple(ids[start : start + size])))
            start += size
    away = {
        life: [3, 5],  # not on Wednesday and Friday
        sports: [3, 5],
        music: [1, 2, 3, 4],  # Friday only
    }
    resources = _resources(
        lessons,
        periods,
        [homeroom, local_language, life, sports, music],
        required_teacher_rules=_required_teachers({r: spec[2] for r, spec in requirements.items()}),
        required_room_rules=[
            RequiredRoomRule(class_subject_requirement_id=r, room_id=spec[3])
            for r, spec in requirements.items()
            if spec[3] is not None
        ],
        teacher_unavailability=[
            TeacherUnavailability(teacher_id=teacher, time_slot_id=_slot(day, period))
            for teacher, days in away.items()
            for day in days
            for period in periods[day]
        ],
        lesson_blocks=blocks,
    )
    return lessons, resources


def test_fills_a_class_with_no_free_slot() -> None:
    lessons, resources = _full_week_class()

    _assert_valid(schedule_forward_checking(lessons, resources, seed=1), lessons, resources)


# --- Regression: the semester Backtracking could not schedule (Task 104) ---

# The scheduler's input for a real semester (record 84, exported with ids
# only): six classes that each fill every time slot they have, fixed
# slots, 連堂, 合併節 and teachers who come on a few days only.
FULL_SCHOOL_DATA = Path(__file__).with_name("data") / "full_school_semester.json"

_RESOURCE_ITEM_TYPES: dict[str, type] = {
    "teacher_unavailability": TeacherUnavailability,
    "required_teacher_rules": RequiredTeacherRule,
    "required_room_rules": RequiredRoomRule,
    "time_slots": TimeSlotInfo,
    "active_statuses": ActiveStatusInfo,
    "requirement_periods": RequirementPeriods,
    "teacher_workload_limits": TeacherWorkloadLimit,
    "time_slot_positions": TimeSlotPosition,
    "default_rooms": DefaultRoom,
    "room_capacities": RoomCapacity,
}


def _load_full_school() -> tuple[list[LessonAssignment], SchedulingResources]:
    data = json.loads(FULL_SCHOOL_DATA.read_text(encoding="utf-8"))
    raw = data["resources"]
    fields: dict[str, object] = {
        name: [item_type(**item) for item in raw[name]] for name, item_type in _RESOURCE_ITEM_TYPES.items()
    }
    fields["time_slot_ids"] = raw["time_slot_ids"]
    fields["teacher_ids"] = raw["teacher_ids"]
    fields["lesson_blocks"] = [
        LessonBlock(item["class_subject_requirement_id"], item["block_no"], tuple(item["lesson_ids"]))
        for item in raw["lesson_blocks"]
    ]
    fields["class_allowed_time_slots"] = [
        ClassAllowedTimeSlots(item["class_id"], frozenset(item["time_slot_ids"]))
        for item in raw["class_allowed_time_slots"]
    ]
    fields["combined_lessons"] = [
        CombinedLesson(
            key=item["key"],
            member_lesson_ids=tuple(tuple(ids) for ids in item["member_lesson_ids"]),
            room_id=item["room_id"],
            teacher_ids=tuple(item["teacher_ids"]),
        )
        for item in raw["combined_lessons"]
    ]
    lessons = [LessonAssignment(**item) for item in data["lessons"]]
    return lessons, SchedulingResources(**fields)  # type: ignore[arg-type]


def test_schedules_the_semester_backtracking_gave_up_on() -> None:
    lessons, resources = _load_full_school()

    assert schedule_backtracking(lessons, resources).failure_type == "SEARCH_LIMIT_EXCEEDED"
    result = schedule_forward_checking(lessons, resources, seed=5, timeout_seconds=90)

    placed = _assert_valid(result, lessons, resources)
    fixed = [lesson for lesson in lessons if lesson.time_slot_id is not None]
    assert fixed
    assert all(placed[lesson.lesson_id].time_slot_id == lesson.time_slot_id for lesson in fixed)
