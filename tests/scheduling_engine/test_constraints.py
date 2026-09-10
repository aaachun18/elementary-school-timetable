"""Tests for the Constraint Engine (scheduling_engine/). Pure Python, no
database, no db_session/client fixtures -- this layer never touches
SQLAlchemy or FastAPI."""

from scheduling_engine.constraints import (
    ActiveStatusConstraint,
    ClassConflictConstraint,
    NonTeachingPeriodConstraint,
    RequiredTeacherConstraint,
    RoomConflictConstraint,
    RoomTypeConstraint,
    TeacherAvailabilityConstraint,
    TeacherConflictConstraint,
    TeacherQualificationConstraint,
)
from scheduling_engine.models.domain import (
    ActiveStatusInfo,
    LessonAssignment,
    RequiredTeacherRule,
    RoomInfo,
    RoomTypeRequirement,
    TeacherQualification,
    TeacherUnavailability,
    TimeSlotInfo,
)


def _assignment(
    lesson_id: int,
    class_subject_requirement_id: int = 1,
    class_id: int = 1,
    subject_id: int = 1,
    teacher_id: int | None = 1,
    time_slot_id: int | None = 1,
    room_id: int | None = 1,
) -> LessonAssignment:
    return LessonAssignment(
        lesson_id=lesson_id,
        class_subject_requirement_id=class_subject_requirement_id,
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


# --- H6 Required Teacher ---


def test_required_teacher_violation_detected() -> None:
    assignments = [
        _assignment(lesson_id=1, class_subject_requirement_id=7, teacher_id=99)
    ]
    constraint = RequiredTeacherConstraint(
        rules=[RequiredTeacherRule(class_subject_requirement_id=7, required_teacher_id=10)]
    )

    assert constraint.validate(assignments) is False
    violations = constraint.explain_violations(assignments)
    assert len(violations) == 1
    assert violations[0].type == "H6_REQUIRED_TEACHER"
    assert violations[0].lesson_id == 1


def test_required_teacher_ok_when_matching() -> None:
    assignments = [
        _assignment(lesson_id=1, class_subject_requirement_id=7, teacher_id=10)
    ]
    constraint = RequiredTeacherConstraint(
        rules=[RequiredTeacherRule(class_subject_requirement_id=7, required_teacher_id=10)]
    )

    assert constraint.validate(assignments) is True
    assert constraint.explain_violations(assignments) == []


def test_required_teacher_ok_when_no_rule_for_requirement() -> None:
    # No rule at all for requirement 7 -> unconstrained, any teacher is fine.
    assignments = [
        _assignment(lesson_id=1, class_subject_requirement_id=7, teacher_id=99)
    ]
    constraint = RequiredTeacherConstraint(rules=[])

    assert constraint.validate(assignments) is True


def test_required_teacher_ignores_unassigned_teacher() -> None:
    assignments = [
        _assignment(lesson_id=1, class_subject_requirement_id=7, teacher_id=None)
    ]
    constraint = RequiredTeacherConstraint(
        rules=[RequiredTeacherRule(class_subject_requirement_id=7, required_teacher_id=10)]
    )

    assert constraint.validate(assignments) is True


# --- H9 Room Type ---


def test_room_type_violation_detected() -> None:
    assignments = [
        _assignment(lesson_id=1, class_subject_requirement_id=7, room_id=50)
    ]
    constraint = RoomTypeConstraint(
        requirements=[
            RoomTypeRequirement(
                class_subject_requirement_id=7, required_room_type="自然教室"
            )
        ],
        rooms=[RoomInfo(room_id=50, room_type="普通教室")],
    )

    assert constraint.validate(assignments) is False
    violations = constraint.explain_violations(assignments)
    assert len(violations) == 1
    assert violations[0].type == "H9_ROOM_TYPE"


def test_room_type_ok_when_matching() -> None:
    assignments = [
        _assignment(lesson_id=1, class_subject_requirement_id=7, room_id=50)
    ]
    constraint = RoomTypeConstraint(
        requirements=[
            RoomTypeRequirement(
                class_subject_requirement_id=7, required_room_type="自然教室"
            )
        ],
        rooms=[RoomInfo(room_id=50, room_type="自然教室")],
    )

    assert constraint.validate(assignments) is True
    assert constraint.explain_violations(assignments) == []


def test_room_type_ok_when_no_requirement() -> None:
    # No RoomTypeRequirement for requirement 7 -> "原班上課", any room is fine.
    assignments = [
        _assignment(lesson_id=1, class_subject_requirement_id=7, room_id=50)
    ]
    constraint = RoomTypeConstraint(
        requirements=[], rooms=[RoomInfo(room_id=50, room_type="普通教室")]
    )

    assert constraint.validate(assignments) is True


def test_room_type_ignores_unassigned_room() -> None:
    assignments = [
        _assignment(lesson_id=1, class_subject_requirement_id=7, room_id=None)
    ]
    constraint = RoomTypeConstraint(
        requirements=[
            RoomTypeRequirement(
                class_subject_requirement_id=7, required_room_type="自然教室"
            )
        ],
        rooms=[],
    )

    assert constraint.validate(assignments) is True


def test_room_type_ok_when_room_id_unknown() -> None:
    # room_id=50 is set (a room WAS assigned), but no RoomInfo exists for
    # it at all -- must not be treated as a type mismatch.
    assignments = [
        _assignment(lesson_id=1, class_subject_requirement_id=7, room_id=50)
    ]
    constraint = RoomTypeConstraint(
        requirements=[
            RoomTypeRequirement(
                class_subject_requirement_id=7, required_room_type="自然教室"
            )
        ],
        rooms=[],  # no RoomInfo for room_id=50
    )

    assert constraint.validate(assignments) is True
    assert constraint.explain_violations(assignments) == []


# --- H11 Non-teaching Period ---


def test_non_teaching_period_violation_detected() -> None:
    assignments = [_assignment(lesson_id=1, time_slot_id=100)]
    constraint = NonTeachingPeriodConstraint(
        time_slots=[TimeSlotInfo(time_slot_id=100, is_teaching_period=False)]
    )

    assert constraint.validate(assignments) is False
    violations = constraint.explain_violations(assignments)
    assert len(violations) == 1
    assert violations[0].type == "H11_NON_TEACHING_PERIOD"


def test_non_teaching_period_ok_when_teaching_period() -> None:
    assignments = [_assignment(lesson_id=1, time_slot_id=100)]
    constraint = NonTeachingPeriodConstraint(
        time_slots=[TimeSlotInfo(time_slot_id=100, is_teaching_period=True)]
    )

    assert constraint.validate(assignments) is True
    assert constraint.explain_violations(assignments) == []


def test_non_teaching_period_ok_when_slot_unknown() -> None:
    # No TimeSlotInfo provided for this slot at all -- don't guess, treat
    # as fine rather than assuming a violation.
    assignments = [_assignment(lesson_id=1, time_slot_id=100)]
    constraint = NonTeachingPeriodConstraint(time_slots=[])

    assert constraint.validate(assignments) is True


def test_non_teaching_period_ignores_unplaced_lesson() -> None:
    assignments = [_assignment(lesson_id=1, time_slot_id=None)]
    constraint = NonTeachingPeriodConstraint(
        time_slots=[TimeSlotInfo(time_slot_id=100, is_teaching_period=False)]
    )

    assert constraint.validate(assignments) is True


# --- H12 Active Status ---


def test_active_status_violation_detected_for_inactive_teacher() -> None:
    assignments = [_assignment(lesson_id=1, teacher_id=10)]
    constraint = ActiveStatusConstraint(
        active_statuses=[
            ActiveStatusInfo(entity_type="teacher", entity_id=10, is_active=False)
        ]
    )

    assert constraint.validate(assignments) is False
    violations = constraint.explain_violations(assignments)
    assert len(violations) == 1
    assert violations[0].type == "H12_ACTIVE_STATUS"


def test_active_status_violation_detected_for_inactive_class() -> None:
    assignments = [_assignment(lesson_id=1, class_id=20)]
    constraint = ActiveStatusConstraint(
        active_statuses=[
            ActiveStatusInfo(entity_type="class", entity_id=20, is_active=False)
        ]
    )

    assert constraint.validate(assignments) is False


def test_active_status_ok_when_all_active() -> None:
    assignments = [_assignment(lesson_id=1, teacher_id=10, class_id=20, room_id=30)]
    constraint = ActiveStatusConstraint(
        active_statuses=[
            ActiveStatusInfo(entity_type="teacher", entity_id=10, is_active=True),
            ActiveStatusInfo(entity_type="class", entity_id=20, is_active=True),
            ActiveStatusInfo(entity_type="room", entity_id=30, is_active=True),
        ]
    )

    assert constraint.validate(assignments) is True
    assert constraint.explain_violations(assignments) == []


def test_active_status_ignores_unassigned_teacher_and_room() -> None:
    # teacher_id/room_id are None -- an unfilled slot isn't "disabled".
    assignments = [
        _assignment(lesson_id=1, teacher_id=None, room_id=None, class_id=20)
    ]
    constraint = ActiveStatusConstraint(
        active_statuses=[
            ActiveStatusInfo(entity_type="class", entity_id=20, is_active=True)
        ]
    )

    assert constraint.validate(assignments) is True
