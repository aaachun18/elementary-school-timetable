"""Tests for the Constraint Engine (scheduling_engine/). Pure Python, no
database, no db_session/client fixtures -- this layer never touches
SQLAlchemy or FastAPI."""

from scheduling_engine.constraints import (
    ClassConflictConstraint,
    RoomConflictConstraint,
    TeacherAvailabilityConstraint,
    TeacherConflictConstraint,
    TeacherQualificationConstraint,
)
from scheduling_engine.models.domain import (
    LessonAssignment,
    TeacherQualification,
    TeacherUnavailability,
)


def _assignment(
    lesson_id: int,
    class_id: int = 1,
    subject_id: int = 1,
    teacher_id: int | None = 1,
    time_slot_id: int | None = 1,
    room_id: int | None = 1,
) -> LessonAssignment:
    return LessonAssignment(
        lesson_id=lesson_id,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
        time_slot_id=time_slot_id,
        room_id=room_id,
    )


# --- H1 Teacher Conflict ---


def test_teacher_conflict_detected() -> None:
    assignments = [
        _assignment(lesson_id=1, teacher_id=10, time_slot_id=100, class_id=1),
        _assignment(lesson_id=2, teacher_id=10, time_slot_id=100, class_id=2),
    ]
    constraint = TeacherConflictConstraint()

    assert constraint.validate(assignments) is False
    violations = constraint.explain_violations(assignments)
    assert len(violations) == 2
    assert {v.lesson_id for v in violations} == {1, 2}
    assert all(v.type == "H1_TEACHER_CONFLICT" for v in violations)
    assert all(v.teacher_id == 10 for v in violations)


def test_teacher_conflict_ok_when_different_time_slots() -> None:
    assignments = [
        _assignment(lesson_id=1, teacher_id=10, time_slot_id=100),
        _assignment(lesson_id=2, teacher_id=10, time_slot_id=200),
    ]
    constraint = TeacherConflictConstraint()

    assert constraint.validate(assignments) is True
    assert constraint.explain_violations(assignments) == []


def test_teacher_conflict_ignores_unassigned_teacher() -> None:
    assignments = [
        _assignment(lesson_id=1, teacher_id=None, time_slot_id=100),
        _assignment(lesson_id=2, teacher_id=None, time_slot_id=100),
    ]
    constraint = TeacherConflictConstraint()

    assert constraint.validate(assignments) is True


# --- H2 Class Conflict ---


def test_class_conflict_detected() -> None:
    assignments = [
        _assignment(lesson_id=1, class_id=20, time_slot_id=100, teacher_id=1),
        _assignment(lesson_id=2, class_id=20, time_slot_id=100, teacher_id=2),
    ]
    constraint = ClassConflictConstraint()

    assert constraint.validate(assignments) is False
    violations = constraint.explain_violations(assignments)
    assert len(violations) == 2
    assert all(v.type == "H2_CLASS_CONFLICT" for v in violations)
    assert all(v.class_id == 20 for v in violations)


def test_class_conflict_ok_when_different_classes() -> None:
    assignments = [
        _assignment(lesson_id=1, class_id=20, time_slot_id=100),
        _assignment(lesson_id=2, class_id=21, time_slot_id=100),
    ]
    constraint = ClassConflictConstraint()

    assert constraint.validate(assignments) is True


# --- H3 Room Conflict ---


def test_room_conflict_detected() -> None:
    assignments = [
        _assignment(lesson_id=1, room_id=30, time_slot_id=100, teacher_id=1),
        _assignment(lesson_id=2, room_id=30, time_slot_id=100, teacher_id=2),
    ]
    constraint = RoomConflictConstraint()

    assert constraint.validate(assignments) is False
    violations = constraint.explain_violations(assignments)
    assert len(violations) == 2
    assert all(v.type == "H3_ROOM_CONFLICT" for v in violations)
    assert {v.lesson_id for v in violations} == {1, 2}
    assert all(v.room_id == 30 for v in violations)


def test_room_conflict_ok_when_room_id_none() -> None:
    # None room_id must never participate in conflict checks, no matter how
    # many share the same time slot.
    assignments = [
        _assignment(lesson_id=1, room_id=None, time_slot_id=100),
        _assignment(lesson_id=2, room_id=None, time_slot_id=100),
        _assignment(lesson_id=3, room_id=None, time_slot_id=100),
    ]
    constraint = RoomConflictConstraint()

    assert constraint.validate(assignments) is True
    assert constraint.explain_violations(assignments) == []


def test_room_conflict_ok_when_different_rooms() -> None:
    assignments = [
        _assignment(lesson_id=1, room_id=30, time_slot_id=100),
        _assignment(lesson_id=2, room_id=31, time_slot_id=100),
    ]
    constraint = RoomConflictConstraint()

    assert constraint.validate(assignments) is True


# --- H4 Teacher Availability ---


def test_teacher_availability_violation_detected() -> None:
    assignments = [_assignment(lesson_id=1, teacher_id=10, time_slot_id=100)]
    constraint = TeacherAvailabilityConstraint(
        unavailability=[TeacherUnavailability(teacher_id=10, time_slot_id=100)]
    )

    assert constraint.validate(assignments) is False
    violations = constraint.explain_violations(assignments)
    assert len(violations) == 1
    assert violations[0].type == "H4_TEACHER_AVAILABILITY"
    assert violations[0].lesson_id == 1


def test_teacher_availability_ok_when_not_in_unavailable_list() -> None:
    assignments = [_assignment(lesson_id=1, teacher_id=10, time_slot_id=100)]
    constraint = TeacherAvailabilityConstraint(
        unavailability=[TeacherUnavailability(teacher_id=10, time_slot_id=999)]
    )

    assert constraint.validate(assignments) is True
    assert constraint.explain_violations(assignments) == []


def test_teacher_availability_ignores_unassigned_teacher() -> None:
    assignments = [_assignment(lesson_id=1, teacher_id=None, time_slot_id=100)]
    constraint = TeacherAvailabilityConstraint(
        unavailability=[TeacherUnavailability(teacher_id=10, time_slot_id=100)]
    )

    assert constraint.validate(assignments) is True


# --- H5 Teacher Qualification ---


def test_teacher_qualification_violation_detected() -> None:
    assignments = [_assignment(lesson_id=1, teacher_id=10, subject_id=5)]
    constraint = TeacherQualificationConstraint(qualifications=[])

    assert constraint.validate(assignments) is False
    violations = constraint.explain_violations(assignments)
    assert len(violations) == 1
    assert violations[0].type == "H5_TEACHER_QUALIFICATION"
    assert violations[0].subject_id == 5


def test_teacher_qualification_ok_when_qualified() -> None:
    assignments = [_assignment(lesson_id=1, teacher_id=10, subject_id=5)]
    constraint = TeacherQualificationConstraint(
        qualifications=[TeacherQualification(teacher_id=10, subject_id=5)]
    )

    assert constraint.validate(assignments) is True
    assert constraint.explain_violations(assignments) == []


def test_teacher_qualification_ignores_unassigned_teacher() -> None:
    assignments = [_assignment(lesson_id=1, teacher_id=None, subject_id=5)]
    constraint = TeacherQualificationConstraint(qualifications=[])

    assert constraint.validate(assignments) is True
