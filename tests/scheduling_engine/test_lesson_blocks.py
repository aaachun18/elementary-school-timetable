"""Task 87: lesson blocks (連堂) in the scheduling engine.

A requirement's lessons can be grouped into blocks (resources.lesson_blocks,
from a lesson_pattern such as "2+1"). A block is placed as one unit: same
day, adjacent teaching periods in block order, one teacher, one room; the
blocks of one requirement go on different days. Pure Python, no database.
"""

from dataclasses import replace

import pytest

from scheduling_engine.algorithms.backtracking import schedule_backtracking
from scheduling_engine.algorithms.blocks import block_windows, teaching_runs
from scheduling_engine.algorithms.greedy import schedule_greedy
from scheduling_engine.algorithms.resources import (
    SchedulingResources,
    build_real_time_constraints,
    lessons_moved_off_fixed_slot,
)
from scheduling_engine.constraints.lesson_block import LessonBlockConstraint
from scheduling_engine.constraints.teacher_workload import TeacherWorkloadConstraint
from scheduling_engine.constraints.weekly_periods import WeeklyPeriodsConstraint
from scheduling_engine.models.domain import (
    LessonAssignment,
    LessonBlock,
    RequiredTeacherRule,
    RequirementPeriods,
    RoomInfo,
    RoomTypeRequirement,
    TeacherQualification,
    TeacherUnavailability,
    TimeSlotInfo,
    TimeSlotPosition,
)
from scheduling_engine.static_feasibility import check_static_feasibility

LUNCH = 5


def slot(weekday: int, period: int) -> int:
    return weekday * 10 + period


def week(days: int = 5, periods: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7)) -> tuple[list[TimeSlotInfo], list[TimeSlotPosition]]:
    """Every day: periods 1-4 and 6-7 teaching, 5 is lunch."""
    infos: list[TimeSlotInfo] = []
    positions: list[TimeSlotPosition] = []
    for weekday in range(1, days + 1):
        for period in periods:
            infos.append(TimeSlotInfo(time_slot_id=slot(weekday, period), is_teaching_period=period != LUNCH))
            positions.append(TimeSlotPosition(time_slot_id=slot(weekday, period), weekday=weekday, period=period))
    return infos, positions


def lesson(lesson_id: int, requirement_id: int, class_id: int, subject_id: int, fixed: int | None = None) -> LessonAssignment:
    return LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=requirement_id,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=None,
        time_slot_id=fixed,
        room_id=None,
    )


def resources(
    lessons: list[LessonAssignment],
    blocks: list[LessonBlock],
    *,
    days: int = 5,
    periods: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7),
    **overrides: object,
) -> SchedulingResources:
    infos, positions = week(days, periods)
    counts: dict[int, int] = {}
    for item in lessons:
        counts[item.class_subject_requirement_id] = counts.get(item.class_subject_requirement_id, 0) + 1
    base: dict[str, object] = dict(
        time_slot_ids=[info.time_slot_id for info in infos],
        teacher_qualifications=[
            TeacherQualification(teacher_id=1, subject_id=10),
            TeacherQualification(teacher_id=2, subject_id=20),
            TeacherQualification(teacher_id=3, subject_id=30),
        ],
        teacher_unavailability=[],
        required_teacher_rules=[],
        room_type_requirements=[],
        rooms=[],
        time_slots=infos,
        active_statuses=[],
        requirement_periods=[RequirementPeriods(class_subject_requirement_id=r, weekly_periods=n) for r, n in counts.items()],
        teacher_workload_limits=[],
        lesson_blocks=blocks,
        time_slot_positions=positions,
    )
    base.update(overrides)
    return SchedulingResources(**base)  # type: ignore[arg-type]


def two_plus_one(requirement_id: int = 1, class_id: int = 1, subject_id: int = 10, first_id: int = 1) -> tuple[list[LessonAssignment], list[LessonBlock]]:
    """A "2+1" requirement: lessons first_id, first_id+1 (block 1) and first_id+2 (block 2)."""
    items = [lesson(first_id + i, requirement_id, class_id, subject_id) for i in range(3)]
    return items, [
        LessonBlock(class_subject_requirement_id=requirement_id, block_no=1, lesson_ids=(first_id, first_id + 1)),
        LessonBlock(class_subject_requirement_id=requirement_id, block_no=2, lesson_ids=(first_id + 2,)),
    ]


def run(algorithm: str, lessons: list[LessonAssignment], res: SchedulingResources):  # type: ignore[no-untyped-def]
    return (schedule_greedy if algorithm == "greedy" else schedule_backtracking)(lessons, res)


def position(res: SchedulingResources, slot_id: int | None) -> tuple[int, int]:
    found = next(p for p in res.time_slot_positions if p.time_slot_id == slot_id)
    return found.weekday, found.period


def all_hard_violations(placed: list[LessonAssignment], res: SchedulingResources) -> list[str]:
    constraints = [
        *build_real_time_constraints(res, include_teacher_workload=True),
        WeeklyPeriodsConstraint(res.requirement_periods),
        TeacherWorkloadConstraint(res.teacher_workload_limits),
        LessonBlockConstraint(res.lesson_blocks, res.time_slot_positions, res.time_slots),
    ]
    return [v.type for c in constraints for v in c.explain_violations(placed)]


def assert_block_rules(placed: list[LessonAssignment], res: SchedulingResources) -> None:
    by_id = {a.lesson_id: a for a in placed}
    weekdays_by_requirement: dict[int, list[int]] = {}
    for block in res.lesson_blocks:
        members = [by_id[i] for i in block.lesson_ids]
        spots = [position(res, m.time_slot_id) for m in members]
        assert len({day for day, _ in spots}) == 1, spots
        periods = [p for _, p in spots]
        assert periods == list(range(periods[0], periods[0] + len(periods))), spots
        assert LUNCH not in periods
        assert len({m.teacher_id for m in members}) == 1
        assert len({m.room_id for m in members}) == 1
        weekdays_by_requirement.setdefault(block.class_subject_requirement_id, []).append(spots[0][0])
    for days in weekdays_by_requirement.values():
        assert len(days) == len(set(days)), days


# --- Windows ---


def test_lunch_breaks_a_run_of_consecutive_periods() -> None:
    res = resources([], [], days=1)

    assert teaching_runs(res) == [[11, 12, 13, 14], [16, 17]]
    assert (14, 16) not in block_windows(2, res)
    assert block_windows(2, res) == [(11, 12), (12, 13), (13, 14), (16, 17)]
    assert block_windows(3, res) == [(11, 12, 13), (12, 13, 14)]


# --- Placing blocks ---


@pytest.mark.parametrize("algorithm", ["greedy", "backtracking"])
def test_two_plus_one_is_a_double_period_and_a_single_on_another_day(algorithm: str) -> None:
    items, blocks = two_plus_one()
    res = resources(items, blocks)

    result = run(algorithm, items, res)

    assert result.success is True
    assert result.state is not None
    assert_block_rules(result.state.assignments, res)
    assert all_hard_violations(result.state.assignments, res) == []


@pytest.mark.parametrize("algorithm", ["greedy", "backtracking"])
def test_triple_block_never_spans_lunch(algorithm: str) -> None:
    # A single "3" block over two days: it must use periods 1-3 or 2-4,
    # never 4-6 or 3-6 across lunch.
    items = [lesson(i, 1, 1, 10) for i in (1, 2, 3)]
    blocks = [LessonBlock(class_subject_requirement_id=1, block_no=1, lesson_ids=(1, 2, 3))]
    res = resources(items, blocks, days=2)

    result = run(algorithm, items, res)

    assert result.success is True
    assert result.state is not None
    periods = sorted(position(res, a.time_slot_id)[1] for a in result.state.assignments)
    assert periods in ([1, 2, 3], [2, 3, 4])
    assert_block_rules(result.state.assignments, res)


@pytest.mark.parametrize("algorithm", ["greedy", "backtracking"])
def test_several_requirements_with_blocks_respect_every_hard_constraint(algorithm: str) -> None:
    # Two classes, the same teacher teaches subject 10 in both, one room of
    # the needed type; plus single lessons with no pattern.
    a, a_blocks = two_plus_one(requirement_id=1, class_id=1, subject_id=10, first_id=1)
    b, b_blocks = two_plus_one(requirement_id=2, class_id=2, subject_id=10, first_id=11)
    singles = [lesson(21, 3, 1, 20), lesson(22, 3, 1, 20), lesson(23, 4, 2, 30)]
    items = [*a, *b, *singles]
    res = resources(
        items,
        [*a_blocks, *b_blocks],
        days=3,
        room_type_requirements=[
            RoomTypeRequirement(class_subject_requirement_id=1, required_room_type="LAB"),
            RoomTypeRequirement(class_subject_requirement_id=2, required_room_type="LAB"),
        ],
        rooms=[RoomInfo(room_id=7, room_type="LAB")],
        teacher_unavailability=[TeacherUnavailability(teacher_id=1, time_slot_id=slot(1, 1))],
    )
    assert check_static_feasibility(items, res).feasible is True

    result = run(algorithm, items, res)

    assert result.success is True
    assert result.state is not None
    assert_block_rules(result.state.assignments, res)
    assert all_hard_violations(result.state.assignments, res) == []
    assert {a.room_id for a in result.state.assignments if a.class_subject_requirement_id in (1, 2)} == {7}


@pytest.mark.parametrize("algorithm", ["greedy", "backtracking"])
def test_a_fixed_lesson_pins_where_its_block_starts(algorithm: str) -> None:
    items, blocks = two_plus_one()
    items[1] = replace(items[1], time_slot_id=slot(2, 3))  # 2nd period of block 1
    res = resources(items, blocks)

    result = run(algorithm, items, res)

    assert result.success is True
    assert result.state is not None
    placed = {a.lesson_id: a.time_slot_id for a in result.state.assignments}
    assert (placed[1], placed[2]) == (slot(2, 2), slot(2, 3))
    assert position(res, placed[3])[0] != 2
    assert lessons_moved_off_fixed_slot(items, result.state.assignments) == []


@pytest.mark.parametrize("algorithm", ["greedy", "backtracking"])
def test_impossible_blocks_fail_instead_of_breaking_a_rule(algorithm: str) -> None:
    # One class, two "3" blocks of different requirements, but only day 1 has
    # three consecutive teaching periods (day 2 only has two). Each
    # requirement alone passes the pre-check; together they can't fit.
    items = [lesson(i, 1, 1, 10) for i in (1, 2, 3)] + [lesson(i, 2, 1, 20) for i in (4, 5, 6)]
    blocks = [
        LessonBlock(class_subject_requirement_id=1, block_no=1, lesson_ids=(1, 2, 3)),
        LessonBlock(class_subject_requirement_id=2, block_no=1, lesson_ids=(4, 5, 6)),
    ]
    res = resources(items, blocks, days=1)
    assert check_static_feasibility(items, res).feasible is True

    result = run(algorithm, items, res)

    assert result.success is False
    assert result.state is None


def test_greedy_reports_every_lesson_of_an_unplaceable_block() -> None:
    items = [lesson(i, 1, 1, 10) for i in (1, 2, 3)] + [lesson(i, 2, 1, 20) for i in (4, 5, 6)]
    blocks = [
        LessonBlock(class_subject_requirement_id=1, block_no=1, lesson_ids=(1, 2, 3)),
        LessonBlock(class_subject_requirement_id=2, block_no=1, lesson_ids=(4, 5, 6)),
    ]
    res = resources(items, blocks, days=1)

    result = schedule_greedy(items, res)

    assert result.success is False
    failed = {failure.lesson_id for failure in result.lesson_failures}
    assert len(failed) == 3
    assert failed in ({1, 2, 3}, {4, 5, 6})
    assert all(failure.reasons for failure in result.lesson_failures)


# --- Without blocks nothing changes ---


@pytest.mark.parametrize("algorithm", ["greedy", "backtracking"])
def test_without_blocks_the_result_is_exactly_the_same(algorithm: str) -> None:
    items = [lesson(1, 1, 1, 10), lesson(2, 1, 1, 10), lesson(3, 2, 1, 20), lesson(4, 3, 2, 10), lesson(5, 3, 2, 10, fixed=slot(2, 2))]
    with_positions = resources(items, [], days=2)
    bare = replace(with_positions, time_slot_positions=[])

    first = run(algorithm, items, with_positions)
    second = run(algorithm, items, bare)

    assert first.success is second.success is True
    assert first.state is not None and second.state is not None
    assert first.state.assignments == second.state.assignments
    if algorithm == "backtracking":
        assert first.backtrack_count == second.backtrack_count  # type: ignore[union-attr]


# --- The block rule itself ---


def test_block_constraint_flags_split_blocks_and_blocks_on_the_same_day() -> None:
    items, blocks = two_plus_one()
    res = resources(items, blocks, days=2)
    rule = LessonBlockConstraint(blocks, res.time_slot_positions, res.time_slots)
    place = lambda item, s, t=1: replace(item, teacher_id=t, time_slot_id=s)  # noqa: E731

    ok = [place(items[0], slot(1, 1)), place(items[1], slot(1, 2)), place(items[2], slot(2, 1))]
    across_lunch = [place(items[0], slot(1, 4)), place(items[1], slot(1, 6)), place(items[2], slot(2, 1))]
    two_teachers = [place(items[0], slot(1, 1)), place(items[1], slot(1, 2), 2), place(items[2], slot(2, 1))]
    reversed_order = [place(items[0], slot(1, 2)), place(items[1], slot(1, 1)), place(items[2], slot(2, 1))]
    same_day = [place(items[0], slot(1, 1)), place(items[1], slot(1, 2)), place(items[2], slot(1, 4))]

    assert rule.explain_violations(ok) == []
    for broken in (across_lunch, two_teachers, reversed_order):
        assert {v.type for v in rule.explain_violations(broken)} == {"BLOCK_NOT_CONSECUTIVE"}
    assert {(v.type, v.lesson_id) for v in rule.explain_violations(same_day)} == {
        ("BLOCK_SAME_DAY", 1),
        ("BLOCK_SAME_DAY", 2),
        ("BLOCK_SAME_DAY", 3),
    }


def test_block_constraint_judges_a_partly_placed_block_by_its_whole_span() -> None:
    """Task 88 (stored timetables): a block with a lesson missing is wrong
    only if it can't be completed where it is; a lesson without a teacher
    is not a second teacher."""
    items, blocks = two_plus_one()
    res = resources(items, blocks, days=2)
    rule = LessonBlockConstraint(blocks, res.time_slot_positions, res.time_slots)
    place = lambda item, s, t=1: replace(item, teacher_id=t, time_slot_id=s)  # noqa: E731

    completable = [place(items[0], slot(1, 1)), place(items[2], slot(2, 1))]
    before_lunch = [place(items[0], slot(1, 4)), place(items[2], slot(2, 1))]
    no_period_before = [place(items[1], slot(1, 1)), place(items[2], slot(2, 1))]
    no_teacher = [place(items[0], slot(1, 1)), place(items[1], slot(1, 2), None), place(items[2], slot(2, 1))]

    assert rule.explain_violations(completable) == []
    assert rule.explain_violations(no_teacher) == []
    for broken in (before_lunch, no_period_before):
        violations = rule.explain_violations(broken)
        assert [(v.type, v.block_no, v.identity_key) for v in violations] == [
            ("BLOCK_NOT_CONSECUTIVE", 1, "BLOCK_NOT_CONSECUTIVE:1:1")
        ]


# --- Pre-checks ---


def static_types(items: list[LessonAssignment], res: SchedulingResources) -> list[str]:
    return sorted(v.type for v in check_static_feasibility(items, res).violations)


def test_precheck_block_longer_than_any_run() -> None:
    items = [lesson(i, 1, 1, 10) for i in (1, 2, 3)]
    blocks = [LessonBlock(class_subject_requirement_id=1, block_no=1, lesson_ids=(1, 2, 3))]
    res = resources(items, blocks, periods=(1, 2, 5, 6, 7))  # runs of 2 and 2

    violations = check_static_feasibility(items, res).violations

    assert [v.type for v in violations] == ["STATIC_BLOCK_TOO_LONG"]
    v = violations[0]
    assert (v.class_subject_requirement_id, v.class_id, v.subject_id, v.lesson_id) == (1, 1, 10, 1)


def test_precheck_more_blocks_than_days() -> None:
    items = [lesson(i, 1, 1, 10) for i in (1, 2, 3)]
    blocks = [LessonBlock(class_subject_requirement_id=1, block_no=n, lesson_ids=(n,)) for n in (1, 2, 3)]
    res = resources(items, blocks, days=2)

    assert static_types(items, res) == ["STATIC_BLOCK_TOO_MANY_DAYS"]


def test_precheck_not_enough_days_with_long_enough_runs() -> None:
    # "3+3": two days, but day 2 has no lunch-free run of three.
    items = [lesson(i, 1, 1, 10) for i in range(1, 7)]
    blocks = [
        LessonBlock(class_subject_requirement_id=1, block_no=1, lesson_ids=(1, 2, 3)),
        LessonBlock(class_subject_requirement_id=1, block_no=2, lesson_ids=(4, 5, 6)),
    ]
    infos, positions = week(1)
    infos += [TimeSlotInfo(time_slot_id=slot(2, p), is_teaching_period=p != LUNCH) for p in (1, 2, 5, 6, 7)]
    positions += [TimeSlotPosition(time_slot_id=slot(2, p), weekday=2, period=p) for p in (1, 2, 5, 6, 7)]
    res = resources(items, blocks, time_slots=infos, time_slot_positions=positions, time_slot_ids=[i.time_slot_id for i in infos])

    assert static_types(items, res) == ["STATIC_BLOCK_NOT_ENOUGH_DAYS"]


@pytest.mark.parametrize(
    ("fixed", "why"),
    [
        ({1: slot(1, 1), 2: slot(2, 2)}, "different days"),
        ({1: slot(1, 1), 2: slot(1, 3)}, "not adjacent"),
        ({1: slot(1, 2), 2: slot(1, 1)}, "out of block order"),
        ({1: slot(1, 4)}, "the block would run into lunch"),
    ],
)
def test_precheck_fixed_lessons_contradicting_their_block(fixed: dict[int, int], why: str) -> None:
    items, blocks = two_plus_one()
    items = [replace(item, time_slot_id=fixed.get(item.lesson_id)) for item in items]
    res = resources(items, blocks)

    assert "STATIC_BLOCK_FIXED_CONFLICT" in static_types(items, res), why


def test_precheck_two_blocks_fixed_to_the_same_day() -> None:
    items, blocks = two_plus_one()
    items[0] = replace(items[0], time_slot_id=slot(3, 1))
    items[2] = replace(items[2], time_slot_id=slot(3, 6))
    res = resources(items, blocks)

    assert static_types(items, res) == ["STATIC_BLOCK_FIXED_SAME_DAY", "STATIC_BLOCK_FIXED_SAME_DAY"]


def test_precheck_required_teacher_unavailable_in_every_window() -> None:
    # Days 1-2; teacher 1 is away at periods 2 and 6 on both days, so no
    # two consecutive periods are free.
    items, blocks = two_plus_one()
    away = [TeacherUnavailability(teacher_id=1, time_slot_id=slot(d, p)) for d in (1, 2) for p in (2, 3, 6)]
    res = resources(
        items,
        blocks,
        days=2,
        teacher_unavailability=away,
        required_teacher_rules=[RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=1)],
    )

    violations = [v for v in check_static_feasibility(items, res).violations if v.type == "STATIC_BLOCK_TEACHER_UNAVAILABLE"]

    assert len(violations) == 1
    assert violations[0].teacher_id == 1
    assert violations[0].lesson_id == 1  # block 1 (the double period)


def test_precheck_passes_blocks_that_can_be_placed() -> None:
    items, blocks = two_plus_one()
    items[1] = replace(items[1], time_slot_id=slot(2, 3))
    res = resources(
        items,
        blocks,
        teacher_unavailability=[TeacherUnavailability(teacher_id=1, time_slot_id=slot(1, 1))],
    )

    result = check_static_feasibility(items, res)

    assert result.feasible is True
    assert result.violations == []
