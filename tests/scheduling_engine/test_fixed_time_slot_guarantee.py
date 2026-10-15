"""Task 81: fixed time slots as a guaranteed rule of the engine.

- A fixed Lesson is only ever placed in its fixed slot (both algorithms,
  several data sets), and mixed runs satisfy every hard constraint.
- check_static_feasibility() reports, before any search, each way a fixed
  slot can never be honored -- naming the Lesson, its class, subject and
  slot -- and does not flag fixed slots that can work.
- A legal fixed slot that loses to another constraint makes the run fail;
  it is never satisfied by breaking that constraint.

Pure Python, no database -- same style as test_fixed_time_slot.py.
"""

import pytest

from scheduling_engine.algorithms.backtracking import schedule_backtracking
from scheduling_engine.algorithms.greedy import schedule_greedy
from scheduling_engine.algorithms.resources import (
    SchedulingResources,
    build_real_time_constraints,
    lessons_moved_off_fixed_slot,
)
from scheduling_engine.constraints.teacher_workload import TeacherWorkloadConstraint
from scheduling_engine.constraints.weekly_periods import WeeklyPeriodsConstraint
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
from scheduling_engine.static_feasibility import check_static_feasibility

TEACHING_SLOTS = [101, 102, 103, 104, 105, 106]
LUNCH = 900


def _lesson(
    lesson_id: int,
    requirement_id: int,
    class_id: int,
    subject_id: int,
    fixed: int | None = None,
) -> LessonAssignment:
    return LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=requirement_id,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=None,
        time_slot_id=fixed,
        room_id=None,
    )


def _resources(lessons: list[LessonAssignment], **overrides: object) -> SchedulingResources:
    """Six teaching slots plus one non-teaching LUNCH slot; teachers 1-3
    qualified for subjects 10/20/30 respectively; weekly periods derived
    from the lessons themselves."""
    periods: dict[int, int] = {}
    for lesson in lessons:
        periods[lesson.class_subject_requirement_id] = (
            periods.get(lesson.class_subject_requirement_id, 0) + 1
        )
    base: dict[str, object] = dict(
        time_slot_ids=[*TEACHING_SLOTS, LUNCH],
        teacher_qualifications=[
            TeacherQualification(teacher_id=1, subject_id=10),
            TeacherQualification(teacher_id=2, subject_id=20),
            TeacherQualification(teacher_id=3, subject_id=30),
        ],
        teacher_unavailability=[],
        required_teacher_rules=[],
        room_type_requirements=[],
        rooms=[],
        time_slots=[
            *(TimeSlotInfo(time_slot_id=slot, is_teaching_period=True) for slot in TEACHING_SLOTS),
            TimeSlotInfo(time_slot_id=LUNCH, is_teaching_period=False),
        ],
        active_statuses=[],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=rid, weekly_periods=count)
            for rid, count in periods.items()
        ],
        teacher_workload_limits=[],
    )
    base.update(overrides)
    return SchedulingResources(**base)  # type: ignore[arg-type]


def _all_hard_violations(
    lessons: list[LessonAssignment], placed: list[LessonAssignment], resources: SchedulingResources
) -> list[str]:
    constraints = build_real_time_constraints(resources, include_teacher_workload=True)
    constraints.append(WeeklyPeriodsConstraint(resources.requirement_periods))
    constraints.append(TeacherWorkloadConstraint(resources.teacher_workload_limits))
    found = [v.type for c in constraints for v in c.explain_violations(placed)]
    found += [f"MOVED_FIXED_{lesson_id}" for lesson_id in lessons_moved_off_fixed_slot(lessons, placed)]
    return found


def _types(lessons: list[LessonAssignment], resources: SchedulingResources) -> list[str]:
    return [v.type for v in check_static_feasibility(lessons, resources).violations]


# --- The fixed slot is always kept ---


@pytest.mark.parametrize("algorithm", ["greedy", "backtracking"])
@pytest.mark.parametrize("fixed_slot", [101, 103, 106])
@pytest.mark.parametrize("extra_lessons", [0, 3, 5])
def test_fixed_lesson_is_always_placed_in_its_fixed_slot(
    algorithm: str, fixed_slot: int, extra_lessons: int
) -> None:
    # The fixed lesson shares its class and teacher with the others, so any
    # slot it does not hold is a slot they compete for.
    lessons = [_lesson(1, 1, class_id=1, subject_id=10, fixed=fixed_slot)]
    lessons += [_lesson(10 + i, 2, class_id=1, subject_id=10) for i in range(extra_lessons)]
    resources = _resources(lessons)

    run = schedule_greedy if algorithm == "greedy" else schedule_backtracking
    result = run(lessons, resources)

    assert result.success is True
    assert result.state is not None
    placed = {a.lesson_id: a for a in result.state.assignments}
    assert placed[1].time_slot_id == fixed_slot
    assert _all_hard_violations(lessons, result.state.assignments, resources) == []


@pytest.mark.parametrize("algorithm", ["greedy", "backtracking"])
def test_mixed_fixed_and_free_lessons_satisfy_every_hard_constraint(algorithm: str) -> None:
    lessons = [
        # class 1: two fixed, two free
        _lesson(1, 1, class_id=1, subject_id=10, fixed=101),
        _lesson(2, 1, class_id=1, subject_id=10),
        _lesson(3, 2, class_id=1, subject_id=20, fixed=104),
        _lesson(4, 2, class_id=1, subject_id=20),
        # class 2: same teachers, one fixed where class 1 is free
        _lesson(5, 3, class_id=2, subject_id=10, fixed=102),
        _lesson(6, 3, class_id=2, subject_id=10),
        _lesson(7, 4, class_id=2, subject_id=30),
        _lesson(8, 4, class_id=2, subject_id=30, fixed=101),
    ]
    resources = _resources(
        lessons,
        teacher_unavailability=[TeacherUnavailability(teacher_id=1, time_slot_id=103)],
        required_teacher_rules=[RequiredTeacherRule(class_subject_requirement_id=2, required_teacher_id=2)],
        teacher_workload_limits=[TeacherWorkloadLimit(teacher_id=1, max_weekly_periods=4)],
    )
    assert check_static_feasibility(lessons, resources).feasible is True

    run = schedule_greedy if algorithm == "greedy" else schedule_backtracking
    result = run(lessons, resources)

    assert result.success is True
    assert result.state is not None
    placed = {a.lesson_id: a.time_slot_id for a in result.state.assignments}
    assert (placed[1], placed[3], placed[5], placed[8]) == (101, 104, 102, 101)
    assert _all_hard_violations(lessons, result.state.assignments, resources) == []


def test_lessons_moved_off_fixed_slot_reports_only_moved_fixed_lessons() -> None:
    pending = [_lesson(1, 1, 1, 10, fixed=101), _lesson(2, 1, 1, 10), _lesson(3, 1, 1, 10, fixed=102)]
    placed = [
        _lesson(1, 1, 1, 10, fixed=105),  # moved
        _lesson(2, 1, 1, 10, fixed=103),  # free lesson, any slot is fine
        _lesson(3, 1, 1, 10, fixed=102),  # kept
    ]

    assert lessons_moved_off_fixed_slot(pending, placed) == [1]
    assert lessons_moved_off_fixed_slot(pending, pending) == []


# --- Pre-flight: each impossible fixed slot ---


def test_preflight_flags_unknown_fixed_slot() -> None:
    lessons = [_lesson(1, 1, class_id=1, subject_id=10, fixed=555)]

    violations = check_static_feasibility(lessons, _resources(lessons)).violations

    assert [v.type for v in violations] == ["STATIC_FIXED_SLOT_UNKNOWN"]
    v = violations[0]
    assert (v.lesson_id, v.class_id, v.subject_id, v.time_slot_id) == (1, 1, 10, 555)
    assert v.class_subject_requirement_id == 1
    assert "not one of the school's time slots" in v.message


def test_preflight_flags_non_teaching_fixed_slot() -> None:
    lessons = [_lesson(1, 1, class_id=1, subject_id=10, fixed=LUNCH)]

    violations = check_static_feasibility(lessons, _resources(lessons)).violations

    assert [v.type for v in violations] == ["STATIC_FIXED_SLOT_NON_TEACHING"]
    assert (violations[0].lesson_id, violations[0].time_slot_id) == (1, LUNCH)
    assert "non-teaching period" in violations[0].message


def test_preflight_flags_required_teacher_unavailable_at_fixed_slot() -> None:
    lessons = [_lesson(1, 1, class_id=1, subject_id=10, fixed=102)]
    resources = _resources(
        lessons,
        teacher_qualifications=[
            TeacherQualification(teacher_id=1, subject_id=10),
            TeacherQualification(teacher_id=4, subject_id=10),
        ],
        required_teacher_rules=[RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=1)],
        teacher_unavailability=[TeacherUnavailability(teacher_id=1, time_slot_id=102)],
    )

    violations = check_static_feasibility(lessons, resources).violations

    assert [v.type for v in violations] == ["STATIC_FIXED_SLOT_TEACHER_UNAVAILABLE"]
    v = violations[0]
    assert (v.lesson_id, v.teacher_id, v.class_id, v.subject_id, v.time_slot_id) == (1, 1, 1, 10, 102)


def test_preflight_flags_fixed_slot_where_every_qualified_teacher_is_unavailable() -> None:
    # No required teacher: both qualified teachers are away at 102.
    lessons = [_lesson(1, 1, class_id=1, subject_id=10, fixed=102)]
    resources = _resources(
        lessons,
        teacher_qualifications=[
            TeacherQualification(teacher_id=1, subject_id=10),
            TeacherQualification(teacher_id=4, subject_id=10),
        ],
        teacher_unavailability=[
            TeacherUnavailability(teacher_id=1, time_slot_id=102),
            TeacherUnavailability(teacher_id=4, time_slot_id=102),
        ],
    )

    violations = check_static_feasibility(lessons, resources).violations

    assert [v.type for v in violations] == ["STATIC_FIXED_SLOT_TEACHER_UNAVAILABLE"]
    assert violations[0].teacher_id is None  # no single teacher to blame


def test_preflight_flags_two_fixed_lessons_of_one_class_in_one_slot() -> None:
    lessons = [
        _lesson(1, 1, class_id=1, subject_id=10, fixed=103),
        _lesson(2, 2, class_id=1, subject_id=20, fixed=103),
        _lesson(3, 3, class_id=2, subject_id=30, fixed=103),  # other class: fine
    ]

    violations = check_static_feasibility(lessons, _resources(lessons)).violations

    assert sorted((v.type, v.lesson_id) for v in violations) == [
        ("STATIC_FIXED_SLOT_CLASS_CLASH", 1),
        ("STATIC_FIXED_SLOT_CLASS_CLASH", 2),
    ]
    assert all(v.class_id == 1 and v.time_slot_id == 103 for v in violations)


def test_preflight_flags_two_fixed_lessons_of_one_required_teacher_in_one_slot() -> None:
    # Different classes, both pinned to teacher 1 (one by a required-teacher
    # rule, one because teacher 1 is the subject's only qualified teacher).
    lessons = [
        _lesson(1, 1, class_id=1, subject_id=10, fixed=104),
        _lesson(2, 2, class_id=2, subject_id=10, fixed=104),
    ]
    resources = _resources(
        lessons,
        required_teacher_rules=[RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=1)],
    )

    violations = check_static_feasibility(lessons, resources).violations

    assert sorted((v.type, v.lesson_id, v.teacher_id) for v in violations) == [
        ("STATIC_FIXED_SLOT_TEACHER_CLASH", 1, 1),
        ("STATIC_FIXED_SLOT_TEACHER_CLASH", 2, 1),
    ]


def test_preflight_flags_more_fixed_lessons_than_rooms_of_the_needed_type() -> None:
    lessons = [
        _lesson(1, 1, class_id=1, subject_id=10, fixed=105),
        _lesson(2, 2, class_id=2, subject_id=20, fixed=105),
    ]
    resources = _resources(
        lessons,
        room_type_requirements=[
            RoomTypeRequirement(class_subject_requirement_id=1, required_room_type="LAB"),
            RoomTypeRequirement(class_subject_requirement_id=2, required_room_type="LAB"),
        ],
        rooms=[RoomInfo(room_id=1, room_type="LAB")],
    )

    assert sorted(_types(lessons, resources)) == ["STATIC_FIXED_SLOT_ROOM_SHORTAGE"] * 2


def test_preflight_reports_every_problem_together() -> None:
    lessons = [
        _lesson(1, 1, class_id=1, subject_id=10, fixed=LUNCH),
        _lesson(2, 2, class_id=2, subject_id=20, fixed=101),
        _lesson(3, 3, class_id=2, subject_id=30, fixed=101),
    ]

    result = check_static_feasibility(lessons, _resources(lessons))

    assert result.feasible is False
    assert sorted(v.type for v in result.violations) == [
        "STATIC_FIXED_SLOT_CLASS_CLASH",
        "STATIC_FIXED_SLOT_CLASS_CLASH",
        "STATIC_FIXED_SLOT_NON_TEACHING",
    ]


# --- Pre-flight: no false alarms ---


def test_preflight_passes_fixed_slots_that_can_work() -> None:
    lessons = [
        # same slot, different classes, different teachers
        _lesson(1, 1, class_id=1, subject_id=10, fixed=101),
        _lesson(2, 2, class_id=2, subject_id=20, fixed=101),
        # teacher 1 is away at 102 but teacher 4 can teach subject 10 then
        _lesson(3, 3, class_id=3, subject_id=10, fixed=102),
        # one LAB lesson per slot, one LAB room
        _lesson(4, 4, class_id=4, subject_id=30, fixed=103),
        _lesson(5, 5, class_id=5, subject_id=30, fixed=104),
        _lesson(6, 6, class_id=1, subject_id=10),  # not fixed at all
    ]
    resources = _resources(
        lessons,
        teacher_qualifications=[
            TeacherQualification(teacher_id=1, subject_id=10),
            TeacherQualification(teacher_id=4, subject_id=10),
            TeacherQualification(teacher_id=2, subject_id=20),
            TeacherQualification(teacher_id=3, subject_id=30),
        ],
        teacher_unavailability=[TeacherUnavailability(teacher_id=1, time_slot_id=102)],
        room_type_requirements=[
            RoomTypeRequirement(class_subject_requirement_id=4, required_room_type="LAB"),
            RoomTypeRequirement(class_subject_requirement_id=5, required_room_type="LAB"),
        ],
        rooms=[RoomInfo(room_id=1, room_type="LAB")],
    )

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is True
    assert result.violations == []
    assert schedule_backtracking(lessons, resources).success is True


def test_preflight_ignores_lessons_without_a_fixed_slot() -> None:
    lessons = [_lesson(i, 1, class_id=1, subject_id=10) for i in range(1, 4)]

    assert check_static_feasibility(lessons, _resources(lessons)).violations == []


# --- A legal fixed slot that loses to another constraint ---


@pytest.mark.parametrize("algorithm", ["greedy", "backtracking"])
def test_fixed_slot_competing_with_workload_limit_fails_instead_of_breaking_it(
    algorithm: str,
) -> None:
    # Teacher 1 is subject 10's only teacher (no required-teacher rule, so
    # the static workload check cannot see it) and may teach 1 period a
    # week; two lessons, one fixed. No valid timetable exists.
    lessons = [
        _lesson(1, 1, class_id=1, subject_id=10, fixed=103),
        _lesson(2, 2, class_id=2, subject_id=10),
    ]
    resources = _resources(
        lessons, teacher_workload_limits=[TeacherWorkloadLimit(teacher_id=1, max_weekly_periods=1)]
    )
    assert check_static_feasibility(lessons, resources).feasible is True

    run = schedule_greedy if algorithm == "greedy" else schedule_backtracking
    result = run(lessons, resources)

    assert result.success is False
    assert result.state is None


def test_fixed_slot_taking_the_only_free_slot_fails_instead_of_moving() -> None:
    # Class 1 needs two lessons but the school has a single teaching slot,
    # which the fixed lesson holds: the free lesson has nowhere to go, and
    # the fixed one is never moved to make room.
    lessons = [
        _lesson(1, 1, class_id=1, subject_id=10, fixed=101),
        _lesson(2, 2, class_id=1, subject_id=20),
    ]
    resources = _resources(
        lessons,
        time_slot_ids=[101, LUNCH],
        time_slots=[
            TimeSlotInfo(time_slot_id=101, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=LUNCH, is_teaching_period=False),
        ],
    )
    assert check_static_feasibility(lessons, resources).feasible is True

    result = schedule_backtracking(lessons, resources)

    assert result.success is False
    assert result.state is None
    assert result.failure_type == "DEFINITELY_INFEASIBLE"
