"""導師 rule (scheduling_engine/algorithms/homeroom.py, used by the Forward
Checking Scheduler): a 導師 is kept off other classes' lessons without a
required teacher whenever a timetable allows it; otherwise the timetable
has as few such periods as possible. Pure Python, no database."""

from scheduling_engine.algorithms.blocks import block_constraints
from scheduling_engine.algorithms.forward_checking import schedule_forward_checking
from scheduling_engine.algorithms.homeroom import build_homeroom_rule, reduce_cross_homeroom
from scheduling_engine.algorithms.resources import SchedulingResources, build_real_time_constraints
from scheduling_engine.models.domain import (
    CombinedLesson,
    HomeroomTeacher,
    LessonAssignment,
    RequiredTeacherRule,
    RequirementPeriods,
    TeacherUnavailability,
    TeacherWorkloadLimit,
    TimeSlotInfo,
    TimeSlotPosition,
)

# Monday and Tuesday, periods 1-3: slots 11-13, 21-23.
SLOTS = [day * 10 + period for day in (1, 2) for period in (1, 2, 3)]
# 導師 of class 1 / class 2, and a teacher who is no 導師.
HOMEROOM_1, HOMEROOM_2, SUBJECT_TEACHER = 1, 2, 3
SEEDS = range(8)


def _lesson(lesson_id: int, requirement_id: int, class_id: int) -> LessonAssignment:
    return LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=requirement_id,
        class_id=class_id,
        subject_id=requirement_id,
        teacher_id=None,
        time_slot_id=None,
        room_id=None,
    )


def _resources(lessons: list[LessonAssignment], **overrides: object) -> SchedulingResources:
    counts: dict[int, int] = {}
    for lesson in lessons:
        counts[lesson.class_subject_requirement_id] = counts.get(lesson.class_subject_requirement_id, 0) + 1
    base: dict[str, object] = dict(
        time_slot_ids=list(SLOTS),
        teacher_ids=[HOMEROOM_1, HOMEROOM_2, SUBJECT_TEACHER],
        teacher_unavailability=[],
        required_teacher_rules=[],
        required_room_rules=[],
        time_slots=[TimeSlotInfo(time_slot_id=slot, is_teaching_period=True) for slot in SLOTS],
        time_slot_positions=[
            TimeSlotPosition(time_slot_id=slot, weekday=slot // 10, period=slot % 10) for slot in SLOTS
        ],
        active_statuses=[],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=requirement, weekly_periods=count)
            for requirement, count in counts.items()
        ],
        teacher_workload_limits=[],
        homeroom_teachers=[
            HomeroomTeacher(teacher_id=HOMEROOM_1, class_id=1),
            HomeroomTeacher(teacher_id=HOMEROOM_2, class_id=2),
        ],
    )
    base.update(overrides)
    return SchedulingResources(**base)  # type: ignore[arg-type]


def _cross_periods(assignments: list[LessonAssignment], resources: SchedulingResources) -> int:
    return build_homeroom_rule(resources).count(assignments)


def _assert_valid(assignments: list[LessonAssignment], resources: SchedulingResources) -> None:
    constraints = [
        *build_real_time_constraints(resources, include_teacher_workload=True),
        *block_constraints(resources),
    ]
    for constraint in constraints:
        assert constraint.explain_violations(assignments) == []


def _two_classes() -> list[LessonAssignment]:
    """Class 1: requirements 1 (3 lessons) and 2 (2 lessons); class 2:
    requirements 3 (3 lessons) and 4 (2 lessons)."""
    return [
        _lesson(1, 1, 1), _lesson(2, 1, 1), _lesson(3, 1, 1),
        _lesson(4, 2, 1), _lesson(5, 2, 1),
        _lesson(6, 3, 2), _lesson(7, 3, 2), _lesson(8, 3, 2),
        _lesson(9, 4, 2), _lesson(10, 4, 2),
    ]  # fmt: skip


def test_homeroom_teacher_never_teaches_another_class_when_possible() -> None:
    lessons = _two_classes()
    resources = _resources(lessons)
    for seed in SEEDS:
        result = schedule_forward_checking(lessons, resources, seed=seed)
        assert result.success and result.state is not None
        assert result.homeroom_rule_relaxed is False
        assert result.cross_homeroom_periods == 0
        for assignment in result.state.assignments:
            if assignment.teacher_id == HOMEROOM_1:
                assert assignment.class_id == 1
            if assignment.teacher_id == HOMEROOM_2:
                assert assignment.class_id == 2
        _assert_valid(result.state.assignments, resources)


def test_rule_is_relaxed_with_fewest_cross_periods_when_it_cannot_hold() -> None:
    """導師 2 is never available, and the subject teacher may teach only 1
    period: class 2's two 1-period requirements need 導師 1 for one of them
    -- the timetable is still produced, with exactly 1 cross period."""
    lessons = [_lesson(1, 1, 1), _lesson(2, 3, 2), _lesson(3, 4, 2)]
    resources = _resources(
        lessons,
        teacher_unavailability=[TeacherUnavailability(teacher_id=HOMEROOM_2, time_slot_id=slot) for slot in SLOTS],
        teacher_workload_limits=[TeacherWorkloadLimit(teacher_id=SUBJECT_TEACHER, max_weekly_periods=1)],
    )
    for seed in SEEDS:
        result = schedule_forward_checking(lessons, resources, seed=seed)
        assert result.success and result.state is not None
        assert result.homeroom_rule_relaxed is True
        assert result.cross_homeroom_periods == 1
        assert _cross_periods(result.state.assignments, resources) == 1
        _assert_valid(result.state.assignments, resources)


def test_relaxed_search_minimizes_over_several_requirements() -> None:
    """Class 2 has three 1-period requirements and 導師 2 is never
    available; the subject teacher can take 2 of them, so the minimum is 1
    cross period (not 3)."""
    lessons = [_lesson(1, 3, 2), _lesson(2, 4, 2), _lesson(3, 5, 2)]
    resources = _resources(
        lessons,
        teacher_unavailability=[TeacherUnavailability(teacher_id=HOMEROOM_2, time_slot_id=slot) for slot in SLOTS],
        teacher_workload_limits=[TeacherWorkloadLimit(teacher_id=SUBJECT_TEACHER, max_weekly_periods=2)],
    )
    for seed in SEEDS:
        result = schedule_forward_checking(lessons, resources, seed=seed)
        assert result.success and result.state is not None
        assert result.cross_homeroom_periods == 1
        _assert_valid(result.state.assignments, resources)


def test_rule_never_makes_a_possible_timetable_fail() -> None:
    """Only the two 導師 take part and 導師 2 is never available: class 2's
    lessons can only be taught by 導師 1 -- every one of them is a cross
    period, and the timetable is still produced."""
    lessons = _two_classes()
    resources = _resources(
        lessons,
        teacher_ids=[HOMEROOM_1, HOMEROOM_2],
        teacher_unavailability=[TeacherUnavailability(teacher_id=HOMEROOM_2, time_slot_id=slot) for slot in SLOTS],
    )
    result = schedule_forward_checking(lessons, resources, seed=0)
    assert result.success is False  # 導師 1 alone cannot teach 10 lessons in 6 slots.

    lessons = [_lesson(1, 1, 1), _lesson(2, 1, 1), _lesson(3, 3, 2), _lesson(4, 4, 2)]
    resources = _resources(
        lessons,
        teacher_ids=[HOMEROOM_1, HOMEROOM_2],
        teacher_unavailability=[TeacherUnavailability(teacher_id=HOMEROOM_2, time_slot_id=slot) for slot in SLOTS],
    )
    result = schedule_forward_checking(lessons, resources, seed=0)
    assert result.success and result.state is not None
    assert result.homeroom_rule_relaxed is True
    assert result.cross_homeroom_periods == 2
    _assert_valid(result.state.assignments, resources)


def test_required_teacher_is_not_a_cross_period() -> None:
    """A requirement naming 導師 1 as its required teacher in class 2 is
    the school's choice: allowed, not counted, and the rule is not
    relaxed."""
    lessons = _two_classes()
    resources = _resources(
        lessons,
        required_teacher_rules=[RequiredTeacherRule(class_subject_requirement_id=4, required_teacher_id=HOMEROOM_1)],
    )
    result = schedule_forward_checking(lessons, resources, seed=0)
    assert result.success and result.state is not None
    assert result.homeroom_rule_relaxed is False
    assert result.cross_homeroom_periods == 0
    assert {a.teacher_id for a in result.state.assignments if a.class_subject_requirement_id == 4} == {HOMEROOM_1}


def test_named_combined_lesson_teacher_is_not_a_cross_period() -> None:
    """A 合併節 whose teacher is named (導師 1, for class 1) also teaches
    class 2's member lesson: not counted."""
    lessons = [_lesson(1, 1, 1), _lesson(2, 3, 2)]
    resources = _resources(
        lessons,
        required_teacher_rules=[RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=HOMEROOM_1)],
        combined_lessons=[
            CombinedLesson(key="c1", member_lesson_ids=((1,), (2,)), room_id=None, teacher_ids=(HOMEROOM_1,))
        ],
    )
    result = schedule_forward_checking(lessons, resources, seed=0)
    assert result.success and result.state is not None
    assert result.homeroom_rule_relaxed is False
    assert result.cross_homeroom_periods == 0


def test_without_homeroom_teachers_nothing_changes() -> None:
    lessons = _two_classes()
    with_rule_off = _resources(lessons, homeroom_teachers=[])
    result = schedule_forward_checking(lessons, with_rule_off, seed=3)
    again = schedule_forward_checking(lessons, with_rule_off, seed=3)
    assert result.success and again.success
    assert result.state is not None and again.state is not None
    assert result.state.assignments == again.state.assignments
    assert result.homeroom_rule_relaxed is False


def test_same_seed_gives_same_timetable_when_relaxed() -> None:
    lessons = [_lesson(1, 3, 2), _lesson(2, 4, 2), _lesson(3, 5, 2)]
    resources = _resources(
        lessons,
        teacher_unavailability=[TeacherUnavailability(teacher_id=HOMEROOM_2, time_slot_id=slot) for slot in SLOTS],
        teacher_workload_limits=[TeacherWorkloadLimit(teacher_id=SUBJECT_TEACHER, max_weekly_periods=2)],
    )
    first = schedule_forward_checking(lessons, resources, seed=5)
    second = schedule_forward_checking(lessons, resources, seed=5)
    assert first.state is not None and second.state is not None
    assert first.state.assignments == second.state.assignments


def test_impossible_timetable_still_fails_without_partial_result() -> None:
    """More lessons than class 1 has time slots: no timetable, 導師 or not."""
    lessons = [_lesson(lesson_id, 1, 1) for lesson_id in range(1, 8)]
    resources = _resources(lessons)
    result = schedule_forward_checking(lessons, resources, seed=0)
    assert result.success is False
    assert result.state is None


def test_reduce_cross_homeroom_hands_requirement_to_free_teacher() -> None:
    lessons = [_lesson(1, 3, 2), _lesson(2, 3, 2)]
    resources = _resources(lessons)
    placed = [
        LessonAssignment(1, 3, 2, 3, HOMEROOM_1, 11, None),
        LessonAssignment(2, 3, 2, 3, HOMEROOM_1, 12, None),
    ]
    constraints = build_real_time_constraints(resources, include_teacher_workload=True)
    result = reduce_cross_homeroom(placed, resources, build_homeroom_rule(resources), constraints)
    # 導師 2 (the class's own) is tried before the subject teacher.
    assert {a.teacher_id for a in result} == {HOMEROOM_2}
    assert [a.time_slot_id for a in result] == [11, 12]


def test_reduce_cross_homeroom_keeps_change_out_when_teacher_is_busy() -> None:
    lessons = [_lesson(1, 3, 2), _lesson(2, 1, 1), _lesson(3, 2, 1)]
    resources = _resources(lessons, teacher_ids=[HOMEROOM_1, HOMEROOM_2])
    placed = [
        LessonAssignment(1, 3, 2, 3, HOMEROOM_1, 11, None),
        # 導師 2 is busy in slot 11 (teaching class 1 -- itself cross).
        LessonAssignment(2, 1, 1, 1, HOMEROOM_2, 11, None),
        LessonAssignment(3, 2, 1, 2, HOMEROOM_1, 12, None),
    ]
    constraints = build_real_time_constraints(resources, include_teacher_workload=True)
    result = reduce_cross_homeroom(placed, resources, build_homeroom_rule(resources), constraints)
    assert result == placed
