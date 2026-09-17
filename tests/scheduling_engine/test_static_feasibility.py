"""Tests for the Task 23 pre-search static feasibility checks
(scheduling_engine/static_feasibility.py). Pure Python, no database, no
db_session/client fixtures -- mirrors the style of test_greedy.py /
test_backtracking.py."""

from scheduling_engine.algorithms.resources import SchedulingResources
from scheduling_engine.models.domain import (
    ActiveStatusInfo,
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


def _pending_lesson(
    lesson_id: int,
    class_subject_requirement_id: int,
    class_id: int,
    subject_id: int,
) -> LessonAssignment:
    return LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=class_subject_requirement_id,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=None,
        time_slot_id=None,
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


# --- Feasible baseline: none of the three checks should ever fire on
# ordinary, well-formed input. ---


def test_static_feasibility_passes_with_ample_resources() -> None:
    lessons = [
        _pending_lesson(
            lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
        )
    ]
    resources = _empty_resources(
        time_slot_ids=[100, 200],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=6)
        ],
        teacher_qualifications=[TeacherQualification(teacher_id=6, subject_id=10)],
        teacher_workload_limits=[
            TeacherWorkloadLimit(teacher_id=6, max_weekly_periods=10)
        ],
        active_statuses=[
            ActiveStatusInfo(entity_type="teacher", entity_id=6, is_active=True),
            ActiveStatusInfo(entity_type="class", entity_id=1, is_active=True),
            ActiveStatusInfo(entity_type="subject", entity_id=10, is_active=True),
        ],
    )

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is True
    assert result.violations == []
    assert result.lesson_failures == []


# --- Check 1: teacher workload exceeded ---
# Reproduces the exact 楊老師 scenario from the Task 21/22 investigation:
# one teacher pinned via required_teacher_id across MULTIPLE requirements,
# whose combined Lesson count exceeds max_weekly_periods.


def test_static_feasibility_detects_teacher_workload_exceeded() -> None:
    lessons = [
        # Requirement 1: 3 lessons, all pinned to teacher 6.
        _pending_lesson(1, class_subject_requirement_id=1, class_id=7, subject_id=8),
        _pending_lesson(2, class_subject_requirement_id=1, class_id=7, subject_id=8),
        _pending_lesson(3, class_subject_requirement_id=1, class_id=7, subject_id=8),
        # Requirement 2: 3 more lessons, also pinned to teacher 6.
        _pending_lesson(4, class_subject_requirement_id=2, class_id=10, subject_id=8),
        _pending_lesson(5, class_subject_requirement_id=2, class_id=10, subject_id=8),
        _pending_lesson(6, class_subject_requirement_id=2, class_id=10, subject_id=8),
    ]
    resources = _empty_resources(
        time_slot_ids=list(range(100, 120)),  # plenty of time slots
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=6),
            RequiredTeacherRule(class_subject_requirement_id=2, required_teacher_id=6),
        ],
        teacher_qualifications=[TeacherQualification(teacher_id=6, subject_id=8)],
        # 6 lessons required of teacher 6, but their cap is 5.
        teacher_workload_limits=[
            TeacherWorkloadLimit(teacher_id=6, max_weekly_periods=5)
        ],
    )

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is False
    workload_violations = [
        v for v in result.violations if v.type == "STATIC_TEACHER_WORKLOAD_EXCEEDED"
    ]
    assert len(workload_violations) == 1
    assert workload_violations[0].teacher_id == 6
    assert "6" in workload_violations[0].message  # required count mentioned
    assert "5" in workload_violations[0].message  # the cap mentioned

    # No search was even attempted -- confirmed via the API-level test
    # (test_scheduler.py), which checks backtrack_count == 0.


def test_static_feasibility_teacher_workload_ok_when_within_cap() -> None:
    lessons = [
        _pending_lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=8),
        _pending_lesson(2, class_subject_requirement_id=1, class_id=1, subject_id=8),
    ]
    resources = _empty_resources(
        time_slot_ids=[100, 200],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=6)
        ],
        teacher_qualifications=[TeacherQualification(teacher_id=6, subject_id=8)],
        teacher_workload_limits=[
            TeacherWorkloadLimit(teacher_id=6, max_weekly_periods=2)
        ],
    )

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is True


# --- Check 2: teacher availability insufficient ---


def test_static_feasibility_detects_teacher_availability_insufficient() -> None:
    lessons = [
        _pending_lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=8),
        _pending_lesson(2, class_subject_requirement_id=1, class_id=1, subject_id=8),
        _pending_lesson(3, class_subject_requirement_id=1, class_id=1, subject_id=8),
    ]
    resources = _empty_resources(
        # 3 school time slots total...
        time_slot_ids=[100, 200, 300],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=6)
        ],
        teacher_qualifications=[TeacherQualification(teacher_id=6, subject_id=8)],
        # ...but teacher 6 is unavailable for 2 of them, leaving only 1
        # available slot for 3 required lessons.
        teacher_unavailability=[
            TeacherUnavailability(teacher_id=6, time_slot_id=200),
            TeacherUnavailability(teacher_id=6, time_slot_id=300),
        ],
        # Workload cap is generous -- this must be caught by the
        # AVAILABILITY check specifically, not the workload one.
        teacher_workload_limits=[
            TeacherWorkloadLimit(teacher_id=6, max_weekly_periods=10)
        ],
    )

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is False
    availability_violations = [
        v
        for v in result.violations
        if v.type == "STATIC_TEACHER_AVAILABILITY_INSUFFICIENT"
    ]
    assert len(availability_violations) == 1
    assert availability_violations[0].teacher_id == 6
    assert not any(
        v.type == "STATIC_TEACHER_WORKLOAD_EXCEEDED" for v in result.violations
    )


def test_static_feasibility_teacher_availability_ok_when_sufficient() -> None:
    lessons = [
        _pending_lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=8),
    ]
    resources = _empty_resources(
        time_slot_ids=[100, 200],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=6)
        ],
        teacher_qualifications=[TeacherQualification(teacher_id=6, subject_id=8)],
        teacher_unavailability=[
            TeacherUnavailability(teacher_id=6, time_slot_id=200),
        ],
        teacher_workload_limits=[
            TeacherWorkloadLimit(teacher_id=6, max_weekly_periods=10)
        ],
    )

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is True


# --- Check 3: inactive entity conflict ---


def test_static_feasibility_detects_inactive_class() -> None:
    lessons = [
        _pending_lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=8),
    ]
    resources = _empty_resources(
        time_slot_ids=[100],
        active_statuses=[
            ActiveStatusInfo(entity_type="class", entity_id=1, is_active=False),
        ],
    )

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is False
    violations = [
        v for v in result.violations if v.type == "STATIC_INACTIVE_ENTITY_CONFLICT"
    ]
    assert len(violations) == 1
    assert violations[0].class_id == 1
    assert violations[0].class_subject_requirement_id == 1


def test_static_feasibility_detects_inactive_subject() -> None:
    lessons = [
        _pending_lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=8),
    ]
    resources = _empty_resources(
        time_slot_ids=[100],
        active_statuses=[
            ActiveStatusInfo(entity_type="subject", entity_id=8, is_active=False),
        ],
    )

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is False
    violations = [
        v for v in result.violations if v.type == "STATIC_INACTIVE_ENTITY_CONFLICT"
    ]
    assert len(violations) == 1
    assert violations[0].subject_id == 8


def test_static_feasibility_detects_inactive_required_teacher() -> None:
    lessons = [
        _pending_lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=8),
    ]
    resources = _empty_resources(
        time_slot_ids=[100],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=6)
        ],
        teacher_qualifications=[TeacherQualification(teacher_id=6, subject_id=8)],
        teacher_workload_limits=[
            TeacherWorkloadLimit(teacher_id=6, max_weekly_periods=10)
        ],
        active_statuses=[
            ActiveStatusInfo(entity_type="teacher", entity_id=6, is_active=False),
        ],
    )

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is False
    violations = [
        v for v in result.violations if v.type == "STATIC_INACTIVE_ENTITY_CONFLICT"
    ]
    assert len(violations) == 1
    assert violations[0].teacher_id == 6


def test_static_feasibility_inactive_check_deduplicates_per_requirement() -> None:
    """Multiple Lessons for the same requirement must only produce ONE
    inactive-class violation, not one per Lesson."""
    lessons = [
        _pending_lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=8),
        _pending_lesson(2, class_subject_requirement_id=1, class_id=1, subject_id=8),
        _pending_lesson(3, class_subject_requirement_id=1, class_id=1, subject_id=8),
    ]
    resources = _empty_resources(
        time_slot_ids=[100],
        active_statuses=[
            ActiveStatusInfo(entity_type="class", entity_id=1, is_active=False),
        ],
    )

    result = check_static_feasibility(lessons, resources)

    violations = [
        v for v in result.violations if v.type == "STATIC_INACTIVE_ENTITY_CONFLICT"
    ]
    assert len(violations) == 1


# --- All three fire together without interfering with each other ---


def test_static_feasibility_reports_all_three_kinds_independently() -> None:
    lessons = [
        # Requirement 1: overloads teacher 6 (workload).
        _pending_lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=8),
        _pending_lesson(2, class_subject_requirement_id=1, class_id=1, subject_id=8),
        # Requirement 2: teacher 7 has too few available slots.
        _pending_lesson(3, class_subject_requirement_id=2, class_id=2, subject_id=9),
        _pending_lesson(4, class_subject_requirement_id=2, class_id=2, subject_id=9),
        # Requirement 3: an inactive class, otherwise perfectly schedulable.
        _pending_lesson(5, class_subject_requirement_id=3, class_id=99, subject_id=10),
    ]
    resources = _empty_resources(
        time_slot_ids=[100, 200],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=6),
            RequiredTeacherRule(class_subject_requirement_id=2, required_teacher_id=7),
        ],
        teacher_qualifications=[
            TeacherQualification(teacher_id=6, subject_id=8),
            TeacherQualification(teacher_id=7, subject_id=9),
            # Requirement 3's lesson has no required_teacher_id, so it just
            # needs SOME qualified teacher to avoid also tripping the 4th
            # (zero-candidate-teacher) check this test isn't about --
            # see test_static_feasibility_reports_workload_and_zero_
            # candidate_together below for that combination specifically.
            TeacherQualification(teacher_id=50, subject_id=10),
        ],
        teacher_workload_limits=[
            TeacherWorkloadLimit(teacher_id=6, max_weekly_periods=1),  # too low
            TeacherWorkloadLimit(teacher_id=7, max_weekly_periods=10),  # fine
        ],
        teacher_unavailability=[
            # Teacher 7 can only use slot 100 -- 1 slot for 2 required lessons.
            TeacherUnavailability(teacher_id=7, time_slot_id=200),
        ],
        active_statuses=[
            ActiveStatusInfo(entity_type="class", entity_id=99, is_active=False),
        ],
    )

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is False
    types = {v.type for v in result.violations}
    assert types == {
        "STATIC_TEACHER_WORKLOAD_EXCEEDED",
        "STATIC_TEACHER_AVAILABILITY_INSUFFICIENT",
        "STATIC_INACTIVE_ENTITY_CONFLICT",
    }
    assert len(result.violations) == 3
    assert result.lesson_failures == []


# --- Check 4 (Task 38 bug fix): zero candidate teachers at all ---


def test_static_feasibility_detects_zero_candidate_teacher_lesson() -> None:
    lessons = [
        _pending_lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=99),
    ]
    resources = _empty_resources(time_slot_ids=[100])

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is False
    assert result.violations == []
    assert len(result.lesson_failures) == 1
    failure = result.lesson_failures[0]
    assert failure.lesson_id == 1
    assert failure.class_subject_requirement_id == 1
    assert failure.reasons[0].type == "NO_CANDIDATE_TEACHER"


def test_static_feasibility_detects_required_teacher_not_qualified_lesson() -> None:
    """Same H6-not-H5-qualified distinction as
    test_backtracking_reports_required_teacher_not_qualified -- must be
    caught here too, not just inside schedule_backtracking()'s own
    pre-flight, since this check now runs INSTEAD of ever reaching that
    pre-flight whenever check_static_feasibility() is what run_scheduler()
    calls (see this module's docstring)."""
    lessons = [
        _pending_lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=8),
    ]
    resources = _empty_resources(
        time_slot_ids=[100],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=6)
        ],
        # Teacher 6 exists and is qualified for OTHER subjects, but not 8.
        teacher_qualifications=[TeacherQualification(teacher_id=6, subject_id=9)],
    )

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is False
    assert len(result.lesson_failures) == 1
    reason = result.lesson_failures[0].reasons[0]
    assert reason.type == "H6_REQUIRED_TEACHER_NOT_QUALIFIED"
    assert reason.teacher_id == 6


def test_static_feasibility_reports_workload_and_zero_candidate_together() -> None:
    """Task 38 regression: the exact bug a real user hit. A workload
    problem (requirement 1, teacher 6) and a completely separate
    zero-candidate-teacher problem (requirement 2, no one qualified for
    subject 99) in the SAME run used to only ever report the workload one
    -- run_scheduler() returned as soon as check_static_feasibility() found
    ANYTHING, before schedule_backtracking()'s own pre-flight (the only
    place that used to catch zero-candidate lessons) ever got a chance to
    run. Both must now appear in the same StaticFeasibilityResult."""
    lessons = [
        # Requirement 1: overloads teacher 6 (workload) -- unrelated to
        # requirement 2's problem.
        _pending_lesson(1, class_subject_requirement_id=1, class_id=1, subject_id=8),
        _pending_lesson(2, class_subject_requirement_id=1, class_id=1, subject_id=8),
        # Requirement 2: nobody at all is qualified for subject 99.
        _pending_lesson(3, class_subject_requirement_id=2, class_id=2, subject_id=99),
    ]
    resources = _empty_resources(
        time_slot_ids=[100, 200],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=6),
        ],
        teacher_qualifications=[TeacherQualification(teacher_id=6, subject_id=8)],
        teacher_workload_limits=[
            TeacherWorkloadLimit(teacher_id=6, max_weekly_periods=1),  # too low
        ],
    )

    result = check_static_feasibility(lessons, resources)

    assert result.feasible is False

    assert len(result.violations) == 1
    assert result.violations[0].type == "STATIC_TEACHER_WORKLOAD_EXCEEDED"
    assert result.violations[0].teacher_id == 6

    assert len(result.lesson_failures) == 1
    assert result.lesson_failures[0].lesson_id == 3
    assert result.lesson_failures[0].class_subject_requirement_id == 2
    assert result.lesson_failures[0].reasons[0].type == "NO_CANDIDATE_TEACHER"
