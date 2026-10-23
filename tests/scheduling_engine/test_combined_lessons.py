"""共同排課 (combined lessons) and room capacity in the engine: a 合併節 is
placed as one (same slot, same room), its teachers are the members' named
ones -- or one the search picks -- and it counts once for a teacher's
workload and a room's capacity. Pure Python, no database."""

from scheduling_engine.algorithms.backtracking import schedule_backtracking
from scheduling_engine.algorithms.resources import SchedulingResources
from scheduling_engine.constraints.combined_lesson import CombinedLessonConstraint
from scheduling_engine.constraints.room_conflict import RoomConflictConstraint
from scheduling_engine.constraints.teacher_conflict import TeacherConflictConstraint
from scheduling_engine.models.domain import (
    CombinedLesson,
    LessonAssignment,
    LessonBlock,
    RequiredRoomRule,
    RequiredTeacherRule,
    RequirementPeriods,
    RoomCapacity,
    TeacherWorkloadLimit,
    TimeSlotInfo,
    TimeSlotPosition,
    joint_keys,
)
from scheduling_engine.static_feasibility import check_static_feasibility

LAB = 50


def _lesson(lesson_id: int, requirement_id: int, class_id: int, fixed: int | None = None) -> LessonAssignment:
    return LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=requirement_id,
        class_id=class_id,
        subject_id=7,
        teacher_id=None,
        time_slot_id=fixed,
        room_id=None,
    )


def _resources(slots: int, teachers: list[int], **overrides: object) -> SchedulingResources:
    slot_ids = list(range(1, slots + 1))
    base: dict[str, object] = dict(
        time_slot_ids=slot_ids,
        teacher_ids=teachers,
        teacher_unavailability=[],
        required_teacher_rules=[],
        required_room_rules=[],
        time_slots=[TimeSlotInfo(slot_id, True) for slot_id in slot_ids],
        time_slot_positions=[TimeSlotPosition(slot_id, 1, slot_id) for slot_id in slot_ids],
        active_statuses=[],
        requirement_periods=[],
        teacher_workload_limits=[],
    )
    base.update(overrides)
    return SchedulingResources(**base)  # type: ignore[arg-type]


def _combined(*member_lesson_ids: tuple[int, ...], room_id: int | None = None, teachers: tuple[int, ...] = ()) -> CombinedLesson:
    return CombinedLesson(
        key="1:1", member_lesson_ids=member_lesson_ids, room_id=room_id, teacher_ids=teachers
    )


def _by_id(assignments: list[LessonAssignment]) -> dict[int, LessonAssignment]:
    return {assignment.lesson_id: assignment for assignment in assignments}


def test_a_combined_lesson_is_one_period_for_its_one_teacher() -> None:
    """One teacher, at most one period a week: only possible because the
    two classes' lessons are one 合併節."""
    lessons = [_lesson(1, 10, 1), _lesson(2, 20, 2)]
    resources = _resources(
        2,
        [9],
        teacher_workload_limits=[TeacherWorkloadLimit(9, 1)],
        combined_lessons=[_combined((1,), (2,))],
    )

    result = schedule_backtracking(lessons, resources)

    assert result.success and result.state is not None
    placed = _by_id(result.state.assignments)
    assert placed[1].time_slot_id == placed[2].time_slot_id
    assert placed[1].teacher_id == placed[2].teacher_id == 9


def test_members_keep_their_named_teachers_and_share_one_slot() -> None:
    lessons = [_lesson(1, 10, 1), _lesson(2, 20, 2), _lesson(3, 30, 3)]
    resources = _resources(
        3,
        [4, 5, 6],
        required_teacher_rules=[RequiredTeacherRule(10, 4), RequiredTeacherRule(20, 5)],
        combined_lessons=[_combined((1,), (2,), (3,), teachers=(4, 5))],
    )

    result = schedule_backtracking(lessons, resources)

    assert result.success and result.state is not None
    placed = _by_id(result.state.assignments)
    assert len({assignment.time_slot_id for assignment in placed.values()}) == 1
    # Member 3 names no teacher: it gets the first named one.
    assert (placed[1].teacher_id, placed[2].teacher_id, placed[3].teacher_id) == (4, 5, 4)


def test_combined_lesson_uses_its_own_room_counted_once() -> None:
    """Both classes require another room, but the combined lesson is held
    in LAB, which holds one class -- and the 合併節 counts once."""
    lessons = [_lesson(1, 10, 1), _lesson(2, 20, 2)]
    resources = _resources(
        1,
        [9],
        required_room_rules=[RequiredRoomRule(10, 99), RequiredRoomRule(20, 99)],
        combined_lessons=[_combined((1,), (2,), room_id=LAB)],
    )

    result = schedule_backtracking(lessons, resources)

    assert result.success and result.state is not None
    assert {assignment.room_id for assignment in result.state.assignments} == {LAB}


def test_a_room_holds_as_many_classes_as_its_capacity() -> None:
    lessons = [_lesson(1, 10, 1), _lesson(2, 20, 2)]
    rules = [RequiredRoomRule(10, LAB), RequiredRoomRule(20, LAB)]

    one = schedule_backtracking(lessons, _resources(1, [8, 9], required_room_rules=rules))
    two = schedule_backtracking(
        lessons,
        _resources(1, [8, 9], required_room_rules=rules, room_capacities=[RoomCapacity(LAB, 2)]),
    )

    assert not one.success
    assert two.success


def test_room_conflict_counts_a_combined_lesson_once() -> None:
    assignments = [
        LessonAssignment(1, 10, 1, 7, 9, 1, LAB),
        LessonAssignment(2, 20, 2, 7, 9, 1, LAB),
    ]
    keys = joint_keys([_combined((1,), (2,), room_id=LAB)])

    assert RoomConflictConstraint([], keys).validate(assignments)
    assert TeacherConflictConstraint(keys).validate(assignments)
    assert not RoomConflictConstraint([], {}).validate(assignments)
    assert not TeacherConflictConstraint({}).validate(assignments)


def test_a_fixed_lesson_of_one_member_fixes_the_whole_combined_lesson() -> None:
    lessons = [_lesson(1, 10, 1), _lesson(2, 20, 2, fixed=3)]
    resources = _resources(3, [9], combined_lessons=[_combined((1,), (2,))])

    result = schedule_backtracking(lessons, resources)

    assert result.success and result.state is not None
    placed = _by_id(result.state.assignments)
    assert placed[1].time_slot_id == placed[2].time_slot_id == 3


def test_a_combined_block_takes_consecutive_periods_together() -> None:
    lessons = [_lesson(1, 10, 1), _lesson(2, 10, 1), _lesson(3, 20, 2), _lesson(4, 20, 2)]
    resources = _resources(
        3,
        [9],
        lesson_blocks=[LessonBlock(10, 1, (1, 2)), LessonBlock(20, 1, (3, 4))],
        requirement_periods=[RequirementPeriods(10, 2), RequirementPeriods(20, 2)],
        combined_lessons=[_combined((1, 2), (3, 4))],
    )

    result = schedule_backtracking(lessons, resources)

    assert result.success and result.state is not None
    placed = _by_id(result.state.assignments)
    assert placed[1].time_slot_id == placed[3].time_slot_id
    assert placed[2].time_slot_id == placed[4].time_slot_id
    assert placed[2].time_slot_id == placed[1].time_slot_id + 1  # type: ignore[operator]


def test_split_combined_lesson_is_reported() -> None:
    constraint = CombinedLessonConstraint([_combined((1,), (2,))])
    together = [LessonAssignment(1, 10, 1, 7, 9, 1, None), LessonAssignment(2, 20, 2, 7, 9, 1, None)]
    split = [LessonAssignment(1, 10, 1, 7, 9, 1, None), LessonAssignment(2, 20, 2, 7, 9, 2, None)]

    assert constraint.validate(together)
    assert {violation.lesson_id for violation in constraint.explain_violations(split)} == {1, 2}


def test_members_fixed_to_different_slots_fail_the_pre_check() -> None:
    lessons = [_lesson(1, 10, 1, fixed=1), _lesson(2, 20, 2, fixed=2)]
    resources = _resources(2, [9], combined_lessons=[_combined((1,), (2,))])

    result = check_static_feasibility(lessons, resources)

    assert not result.feasible
    assert {violation.type for violation in result.violations} == {"STATIC_COMBINED_FIXED_CONFLICT"}


def test_required_teacher_workload_counts_a_combined_lesson_once() -> None:
    """The same teacher named by both members of two 合併節: two periods,
    not four -- within a maximum of two."""
    lessons = [_lesson(1, 10, 1), _lesson(2, 10, 1), _lesson(3, 20, 2), _lesson(4, 20, 2)]
    resources = _resources(
        2,
        [9],
        required_teacher_rules=[RequiredTeacherRule(10, 9), RequiredTeacherRule(20, 9)],
        teacher_workload_limits=[TeacherWorkloadLimit(9, 2)],
        combined_lessons=[
            CombinedLesson("1:1", ((1,), (3,)), None, (9,)),
            CombinedLesson("1:2", ((2,), (4,)), None, (9,)),
        ],
    )

    assert check_static_feasibility(lessons, resources).feasible
    result = schedule_backtracking(lessons, resources)
    assert result.success
