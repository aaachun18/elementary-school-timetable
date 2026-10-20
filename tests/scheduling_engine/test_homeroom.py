"""Task 92B: the class's homeroom as the fixed room of a lesson held in its
own classroom (原班上課), and the room pre-checks. Task 98: a requirement's
required special room (RequiredRoomRule) replaces room types -- it is that
requirement's one fixed room, winning over the homeroom. Pure Python, no
database."""

from dataclasses import replace

from scheduling_engine.algorithms.backtracking import schedule_backtracking
from scheduling_engine.algorithms.greedy import schedule_greedy
from scheduling_engine.algorithms.resources import (
    SchedulingResources,
    build_lookup_tables,
    candidate_room_ids,
)
from scheduling_engine.models.domain import (
    ActiveStatusInfo,
    DefaultRoom,
    LessonAssignment,
    LessonBlock,
    RequiredRoomRule,
    RequirementPeriods,
    TeacherWorkloadLimit,
    TimeSlotInfo,
    TimeSlotPosition,
)
from scheduling_engine.static_feasibility import check_static_feasibility

# Monday periods 1-3 (slots 1-3), Tuesday periods 1-3 (slots 4-6).
SLOTS = {slot_id: (1 + (slot_id - 1) // 3, 1 + (slot_id - 1) % 3) for slot_id in range(1, 7)}
HOMEROOM, OTHER_HOMEROOM, LAB = 100, 101, 200


def _lesson(lesson_id: int, requirement_id: int, class_id: int, subject_id: int = 10) -> LessonAssignment:
    return LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=requirement_id,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=None,
        time_slot_id=None,
        room_id=None,
    )


def _resources(**overrides: object) -> SchedulingResources:
    """Requirement 1 (class 1) and 2 (class 2): subject 10 in their own
    classroom -- class 1's homeroom is HOMEROOM, class 2 has none;
    requirement 3 (class 1): subject 20 in the required room LAB. Teachers
    6 and 7 take part."""
    base: dict[str, object] = dict(
        time_slot_ids=list(SLOTS),
        teacher_ids=[6, 7],
        teacher_unavailability=[],
        required_teacher_rules=[],
        required_room_rules=[RequiredRoomRule(class_subject_requirement_id=3, room_id=LAB)],
        time_slots=[TimeSlotInfo(time_slot_id=slot_id, is_teaching_period=True) for slot_id in SLOTS],
        active_statuses=[],
        requirement_periods=[],
        teacher_workload_limits=[
            TeacherWorkloadLimit(teacher_id=6, max_weekly_periods=20),
            TeacherWorkloadLimit(teacher_id=7, max_weekly_periods=20),
        ],
        time_slot_positions=[
            TimeSlotPosition(time_slot_id=slot_id, weekday=weekday, period=period)
            for slot_id, (weekday, period) in SLOTS.items()
        ],
        default_rooms=[DefaultRoom(class_subject_requirement_id=1, room_id=HOMEROOM)],
    )
    base.update(overrides)
    return SchedulingResources(**base)  # type: ignore[arg-type]


def _periods(lessons: list[LessonAssignment]) -> list[RequirementPeriods]:
    counts: dict[int, int] = {}
    for lesson in lessons:
        counts[lesson.class_subject_requirement_id] = counts.get(lesson.class_subject_requirement_id, 0) + 1
    return [RequirementPeriods(class_subject_requirement_id=r, weekly_periods=n) for r, n in counts.items()]


def _types(lessons: list[LessonAssignment], resources: SchedulingResources) -> list[str]:
    return [v.type for v in check_static_feasibility(lessons, resources).violations]


# --- The only room candidate ---


def test_room_candidate_is_the_homeroom_none_or_the_required_room() -> None:
    tables = build_lookup_tables(_resources())

    assert candidate_room_ids(_lesson(1, 1, 1), tables) == [HOMEROOM]
    assert candidate_room_ids(_lesson(2, 2, 2), tables) == [None]  # no homeroom
    assert candidate_room_ids(_lesson(3, 3, 1, subject_id=20), tables) == [LAB]


def test_required_room_wins_over_the_homeroom() -> None:
    tables = build_lookup_tables(
        _resources(default_rooms=[DefaultRoom(1, HOMEROOM), DefaultRoom(3, HOMEROOM)])
    )

    assert candidate_room_ids(_lesson(3, 3, 1, subject_id=20), tables) == [LAB]


def test_without_default_rooms_every_lesson_without_required_room_has_no_room() -> None:
    tables = build_lookup_tables(_resources(default_rooms=[]))

    assert candidate_room_ids(_lesson(1, 1, 1), tables) == [None]


def test_both_algorithms_hold_the_lessons_in_their_rooms() -> None:
    lessons = [_lesson(1, 1, 1), _lesson(2, 1, 1), _lesson(3, 3, 1, subject_id=20), _lesson(4, 2, 2)]
    resources = _resources(requirement_periods=_periods(lessons))

    for result in (schedule_greedy(lessons, resources), schedule_backtracking(lessons, resources)):
        assert result.success
        assert result.state is not None
        rooms = {a.lesson_id: a.room_id for a in result.state.assignments}
        assert rooms == {1: HOMEROOM, 2: HOMEROOM, 3: LAB, 4: None}


def test_block_gets_one_homeroom_and_a_fixed_lesson_keeps_its_slot() -> None:
    lessons = [_lesson(1, 1, 1), _lesson(2, 1, 1), replace(_lesson(3, 1, 1), time_slot_id=6)]
    resources = _resources(
        requirement_periods=_periods(lessons),
        lesson_blocks=[LessonBlock(class_subject_requirement_id=1, block_no=1, lesson_ids=(1, 2))],
    )

    result = schedule_backtracking(lessons, resources)

    assert result.success and result.state is not None
    placed = {a.lesson_id: a for a in result.state.assignments}
    assert {a.room_id for a in placed.values()} == {HOMEROOM}
    assert placed[3].time_slot_id == 6
    first, second = SLOTS[placed[1].time_slot_id], SLOTS[placed[2].time_slot_id]  # type: ignore[index]
    assert (first[0], first[1] + 1) == second


def test_shared_homeroom_is_kept_apart_by_room_conflict() -> None:
    """Two classes, one homeroom, six lessons, six slots: all in the
    homeroom, never two at once (H3, not a new constraint)."""
    lessons = [_lesson(i, 1, 1) for i in (1, 2, 3)] + [_lesson(i, 2, 2) for i in (4, 5, 6)]
    resources = _resources(
        requirement_periods=_periods(lessons),
        default_rooms=[DefaultRoom(1, HOMEROOM), DefaultRoom(2, HOMEROOM)],
        teacher_ids=[6, 8],
        teacher_workload_limits=[TeacherWorkloadLimit(6, 20), TeacherWorkloadLimit(8, 20)],
    )

    result = schedule_backtracking(lessons, resources)

    assert result.success and result.state is not None
    assert {a.room_id for a in result.state.assignments} == {HOMEROOM}
    assert len({a.time_slot_id for a in result.state.assignments}) == 6


def test_required_room_shared_by_two_classes_is_kept_apart() -> None:
    """Task 98: two classes' science both in LAB -- never at the same time."""
    lessons = [_lesson(i, 3, 1, subject_id=20) for i in (1, 2, 3)] + [
        _lesson(i, 4, 2, subject_id=20) for i in (4, 5, 6)
    ]
    resources = _resources(
        requirement_periods=_periods(lessons),
        required_room_rules=[RequiredRoomRule(3, LAB), RequiredRoomRule(4, LAB)],
        teacher_ids=[6, 8],
        teacher_workload_limits=[TeacherWorkloadLimit(6, 20), TeacherWorkloadLimit(8, 20)],
    )

    result = schedule_backtracking(lessons, resources)

    assert result.success and result.state is not None
    assert {a.room_id for a in result.state.assignments} == {LAB}
    assert len({a.time_slot_id for a in result.state.assignments}) == 6


# --- Pre-checks ---


def test_ordinary_rooms_pass_the_pre_checks() -> None:
    lessons = [_lesson(1, 1, 1), _lesson(2, 2, 2), _lesson(3, 3, 1, subject_id=20)]

    assert check_static_feasibility(lessons, _resources()).feasible


def test_shared_homeroom_with_more_lessons_than_teaching_periods() -> None:
    lessons = [_lesson(i, 1, 1) for i in (1, 2, 3, 4)] + [_lesson(i, 2, 2) for i in (5, 6, 7)]
    resources = _resources(default_rooms=[DefaultRoom(1, HOMEROOM), DefaultRoom(2, HOMEROOM)])

    [violation] = check_static_feasibility(lessons, resources).violations

    assert (violation.type, violation.room_id) == ("STATIC_ROOM_OVERBOOKED", HOMEROOM)
    assert "7 堂課" in violation.message and "6 個教學時段" in violation.message


def test_required_room_with_more_lessons_than_teaching_periods() -> None:
    lessons = [_lesson(i, 3, 1, subject_id=20) for i in (1, 2, 3, 4)] + [
        _lesson(i, 4, 2, subject_id=20) for i in (5, 6, 7)
    ]
    resources = _resources(
        required_room_rules=[RequiredRoomRule(3, LAB), RequiredRoomRule(4, LAB)]
    )

    [violation] = check_static_feasibility(lessons, resources).violations

    assert (violation.type, violation.room_id) == ("STATIC_ROOM_OVERBOOKED", LAB)


def test_lessons_of_two_classes_fixed_to_one_slot_in_a_shared_homeroom() -> None:
    lessons = [replace(_lesson(1, 1, 1), time_slot_id=2), replace(_lesson(2, 2, 2), time_slot_id=2)]
    resources = _resources(
        default_rooms=[DefaultRoom(1, HOMEROOM), DefaultRoom(2, HOMEROOM)],
        teacher_ids=[6, 8],
    )

    violations = check_static_feasibility(lessons, resources).violations

    assert [(v.type, v.lesson_id, v.room_id, v.time_slot_id) for v in violations] == [
        ("STATIC_FIXED_SLOT_ROOM_CLASH", 1, HOMEROOM, 2),
        ("STATIC_FIXED_SLOT_ROOM_CLASH", 2, HOMEROOM, 2),
    ]


def test_lessons_of_two_classes_fixed_to_one_slot_in_a_required_room() -> None:
    lessons = [
        replace(_lesson(1, 3, 1, subject_id=20), time_slot_id=2),
        replace(_lesson(2, 4, 2, subject_id=20), time_slot_id=2),
    ]
    resources = _resources(
        required_room_rules=[RequiredRoomRule(3, LAB), RequiredRoomRule(4, LAB)],
        teacher_ids=[6, 8],
    )

    assert _types(lessons, resources) == [
        "STATIC_FIXED_SLOT_ROOM_CLASH",
        "STATIC_FIXED_SLOT_ROOM_CLASH",
    ]


def test_different_homerooms_fixed_to_one_slot_are_fine() -> None:
    lessons = [replace(_lesson(1, 1, 1), time_slot_id=2), replace(_lesson(2, 2, 2), time_slot_id=2)]
    resources = _resources(
        default_rooms=[DefaultRoom(1, HOMEROOM), DefaultRoom(2, OTHER_HOMEROOM)],
        teacher_ids=[6, 8],
    )

    assert check_static_feasibility(lessons, resources).feasible


def test_inactive_homeroom_is_an_inactive_entity() -> None:
    resources = _resources(active_statuses=[ActiveStatusInfo("room", HOMEROOM, False)])

    [violation] = check_static_feasibility([_lesson(1, 1, 1)], resources).violations

    assert (violation.type, violation.room_id, violation.class_subject_requirement_id) == (
        "STATIC_INACTIVE_ENTITY_CONFLICT", HOMEROOM, 1,
    )


def test_inactive_required_room_is_an_inactive_entity() -> None:
    resources = _resources(active_statuses=[ActiveStatusInfo("room", LAB, False)])

    [violation] = check_static_feasibility(
        [_lesson(3, 3, 1, subject_id=20)], resources
    ).violations

    assert (violation.type, violation.room_id, violation.class_subject_requirement_id) == (
        "STATIC_INACTIVE_ENTITY_CONFLICT", LAB, 3,
    )
