"""Tests for the Greedy Scheduler (scheduling_engine/algorithms/greedy.py).
Pure Python, no database, no db_session/client fixtures."""

from scheduling_engine.algorithms.greedy import SchedulingResources, schedule_greedy
from scheduling_engine.models.domain import (
    LessonAssignment,
    RequiredTeacherRule,
    RequirementPeriods,
    TeacherQualification,
    TeacherUnavailability,
    TeacherWorkloadLimit,
    TimeSlotInfo,
)


def _pending_lesson(
    lesson_id: int,
    class_subject_requirement_id: int,
    class_id: int,
    subject_id: int,
) -> LessonAssignment:
    """An unplaced Lesson -- the "to-do list" input schedule_greedy() takes.
    teacher_id/time_slot_id/room_id all None, matching how a real Schedule
    row looks before anything has been filled in."""
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


# --- Simple success ---


def test_greedy_schedules_successfully_with_ample_resources() -> None:
    lessons = [
        _pending_lesson(
            lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
        ),
        _pending_lesson(
            lesson_id=2, class_subject_requirement_id=2, class_id=1, subject_id=20
        ),
    ]
    resources = _empty_resources(
        time_slot_ids=[100, 200],
        teacher_qualifications=[
            TeacherQualification(teacher_id=1, subject_id=10),
            TeacherQualification(teacher_id=1, subject_id=20),
        ],
        time_slots=[
            TimeSlotInfo(time_slot_id=100, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=200, is_teaching_period=True),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=2, weekly_periods=1),
        ],
    )

    result = schedule_greedy(lessons, resources)

    assert result.success is True
    assert result.state is not None
    assert result.lesson_failures == []
    assert result.post_hoc_violations == []
    assert len(result.state.assignments) == 2
    # Same teacher for both lessons -> H1 forces them into different slots.
    assert {a.time_slot_id for a in result.state.assignments} == {100, 200}


# --- MRV: the required-teacher (single-candidate) lesson must be placed
# first, even when it appears SECOND in the input list. ---


def test_greedy_mrv_prioritizes_required_teacher_lesson() -> None:
    # Lesson A: required teacher 10, who is only available at slot 100.
    lesson_a = _pending_lesson(
        lesson_id=100, class_subject_requirement_id=1, class_id=1, subject_id=10
    )
    # Lesson B: two candidate teachers (10 and 11), no required-teacher
    # rule -- flexible. Listed BEFORE lesson A in the input.
    lesson_b = _pending_lesson(
        lesson_id=200, class_subject_requirement_id=2, class_id=2, subject_id=20
    )

    resources = _empty_resources(
        time_slot_ids=[100, 200],
        teacher_qualifications=[
            # H5 still applies even when H6 pins a required teacher -- a
            # required teacher must also hold the underlying qualification.
            TeacherQualification(teacher_id=10, subject_id=10),
            # Order matters: teacher 10 is tried before 11 for subject 20.
            TeacherQualification(teacher_id=10, subject_id=20),
            TeacherQualification(teacher_id=11, subject_id=20),
        ],
        teacher_unavailability=[
            # Teacher 10's ONLY viable slot is 100.
            TeacherUnavailability(teacher_id=10, time_slot_id=200),
        ],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=10)
        ],
        time_slots=[
            TimeSlotInfo(time_slot_id=100, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=200, is_teaching_period=True),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=2, weekly_periods=1),
        ],
    )

    # Lesson B listed first on purpose: if MRV were NOT applied (naive
    # input-order processing), B would be tried first, greedily claim
    # teacher 10 @ slot 100 (the first candidate/slot it tries), and then
    # A (which can ONLY use teacher 10 @ slot 100) would have no valid
    # candidate left -- the whole run would fail.
    result = schedule_greedy([lesson_b, lesson_a], resources)

    assert result.success is True
    assert result.state is not None
    # MRV reordered processing: A (1 candidate teacher) went first, even
    # though it was second in the input list.
    assert result.state.assignments[0].lesson_id == 100
    assignment_by_lesson = {a.lesson_id: a for a in result.state.assignments}
    assert assignment_by_lesson[100].teacher_id == 10
    assert assignment_by_lesson[100].time_slot_id == 100
    # B had to fall back to the OTHER qualified teacher, since 10 was
    # already taken by A at the only slot 10 is available for.
    assert assignment_by_lesson[200].teacher_id == 11


# --- Failure: insufficient resources -> atomic failure, no partial result ---


def test_greedy_fails_atomically_when_resources_insufficient() -> None:
    # Lesson X: required teacher 10, who is unavailable at the only slot.
    lesson_x = _pending_lesson(
        lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
    )
    # Lesson Y: would succeed perfectly fine on its own.
    lesson_y = _pending_lesson(
        lesson_id=2, class_subject_requirement_id=2, class_id=2, subject_id=20
    )

    resources = _empty_resources(
        time_slot_ids=[100],
        teacher_qualifications=[TeacherQualification(teacher_id=20, subject_id=20)],
        teacher_unavailability=[
            TeacherUnavailability(teacher_id=10, time_slot_id=100)
        ],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=10)
        ],
        time_slots=[TimeSlotInfo(time_slot_id=100, is_teaching_period=True)],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=2, weekly_periods=1),
        ],
    )

    result = schedule_greedy([lesson_x, lesson_y], resources)

    assert result.success is False
    # Atomic: no partial schedule exposed, even though lesson Y alone
    # would have succeeded.
    assert result.state is None
    assert len(result.lesson_failures) == 1
    assert result.lesson_failures[0].lesson_id == 1
    assert result.lesson_failures[0].reasons  # a non-empty explanation


def test_greedy_fails_with_no_candidate_teacher_at_all() -> None:
    lesson = _pending_lesson(
        lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=99
    )
    resources = _empty_resources(
        time_slot_ids=[100],
        time_slots=[TimeSlotInfo(time_slot_id=100, is_teaching_period=True)],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1)
        ],
        # No TeacherQualification for subject_id=99 at all.
    )

    result = schedule_greedy([lesson], resources)

    assert result.success is False
    assert result.state is None
    assert len(result.lesson_failures) == 1
    assert result.lesson_failures[0].reasons[0].type == "NO_CANDIDATE_TEACHER"


# --- H7/H8: whole-batch post-hoc validation ---


def test_greedy_detects_h7_violation_when_lesson_count_is_short() -> None:
    # Only ONE Lesson is actually handed to the algorithm, but
    # requirement_periods says this requirement needs 2 -- every per-lesson
    # placement succeeds (there's only one to place), so this can only be
    # caught by the post-hoc H7 check.
    lesson = _pending_lesson(
        lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
    )
    resources = _empty_resources(
        time_slot_ids=[100],
        teacher_qualifications=[TeacherQualification(teacher_id=1, subject_id=10)],
        time_slots=[TimeSlotInfo(time_slot_id=100, is_teaching_period=True)],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=2)
        ],
    )

    result = schedule_greedy([lesson], resources)

    assert result.success is False
    assert result.state is None
    assert result.lesson_failures == []
    assert len(result.post_hoc_violations) == 1
    assert result.post_hoc_violations[0].type == "H7_WEEKLY_PERIODS"
    assert result.post_hoc_violations[0].class_subject_requirement_id == 1


def test_greedy_detects_h8_violation_when_required_teacher_overloaded() -> None:
    # Three separate requirements all mandate the SAME teacher (H6), who
    # has a max_weekly_periods of 2. Nothing in H1-H6/H9/H11/H12 checks
    # total workload, so all three lessons place successfully in
    # real-time -- only the post-hoc H8 check catches the overload. This
    # is a deliberate consequence of NOT adding real-time H8 pruning (see
    # the Task 19 report's design discussion).
    lessons = [
        _pending_lesson(
            lesson_id=1, class_subject_requirement_id=1, class_id=1, subject_id=10
        ),
        _pending_lesson(
            lesson_id=2, class_subject_requirement_id=2, class_id=2, subject_id=20
        ),
        _pending_lesson(
            lesson_id=3, class_subject_requirement_id=3, class_id=3, subject_id=30
        ),
    ]
    resources = _empty_resources(
        time_slot_ids=[100, 200, 300],
        teacher_qualifications=[
            TeacherQualification(teacher_id=10, subject_id=10),
            TeacherQualification(teacher_id=10, subject_id=20),
            TeacherQualification(teacher_id=10, subject_id=30),
        ],
        required_teacher_rules=[
            RequiredTeacherRule(class_subject_requirement_id=1, required_teacher_id=10),
            RequiredTeacherRule(class_subject_requirement_id=2, required_teacher_id=10),
            RequiredTeacherRule(class_subject_requirement_id=3, required_teacher_id=10),
        ],
        time_slots=[
            TimeSlotInfo(time_slot_id=100, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=200, is_teaching_period=True),
            TimeSlotInfo(time_slot_id=300, is_teaching_period=True),
        ],
        requirement_periods=[
            RequirementPeriods(class_subject_requirement_id=1, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=2, weekly_periods=1),
            RequirementPeriods(class_subject_requirement_id=3, weekly_periods=1),
        ],
        teacher_workload_limits=[
            TeacherWorkloadLimit(teacher_id=10, max_weekly_periods=2)
        ],
    )

    result = schedule_greedy(lessons, resources)

    assert result.success is False
    assert result.state is None
    assert result.lesson_failures == []
    assert len(result.post_hoc_violations) == 1
    assert result.post_hoc_violations[0].type == "H8_TEACHER_MAX_WORKLOAD"
    assert result.post_hoc_violations[0].teacher_id == 10
