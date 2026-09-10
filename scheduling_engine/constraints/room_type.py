from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import (
    LessonAssignment,
    RoomInfo,
    RoomTypeRequirement,
)


class RoomTypeConstraint(BaseConstraint):
    """H9 Room Type: when a ClassSubjectRequirement specifies a required
    room type, the lesson's assigned room must match it. No rule for a
    requirement means "原班上課" -- no room-type restriction at all."""

    VIOLATION_TYPE = "H9_ROOM_TYPE"

    def __init__(
        self,
        requirements: list[RoomTypeRequirement],
        rooms: list[RoomInfo],
    ) -> None:
        self._required_room_type_by_requirement: dict[int, str] = {
            requirement.class_subject_requirement_id: requirement.required_room_type
            for requirement in requirements
        }
        self._room_type_by_room_id: dict[int, str] = {
            room.room_id: room.room_type for room in rooms
        }

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for assignment in assignments:
            required_room_type = self._required_room_type_by_requirement.get(
                assignment.class_subject_requirement_id
            )
            if required_room_type is None:
                continue
            if assignment.room_id is None:
                # Not yet assigned a room -- nothing to compare yet.
                continue
            if assignment.room_id not in self._room_type_by_room_id:
                # No RoomInfo for this room at all -- can't judge a
                # mismatch we have no data for, so don't guess (same
                # "unknown -> not a violation" stance as H11's unknown
                # time slot handling, not "assume it fails").
                continue

            actual_room_type = self._room_type_by_room_id[assignment.room_id]
            if actual_room_type == required_room_type:
                continue

            violations.append(
                ConstraintViolation(
                    type=self.VIOLATION_TYPE,
                    severity=Severity.ERROR,
                    lesson_id=assignment.lesson_id,
                    teacher_id=assignment.teacher_id,
                    class_id=assignment.class_id,
                    subject_id=assignment.subject_id,
                    time_slot_id=assignment.time_slot_id,
                    room_id=assignment.room_id,
                    message=(
                        f"Lesson {assignment.lesson_id} requires room type "
                        f"'{required_room_type}', but room "
                        f"{assignment.room_id} is '{actual_room_type}'."
                    ),
                    suggested_action=(
                        f"Assign a room of type '{required_room_type}'."
                    ),
                )
            )
        return violations
