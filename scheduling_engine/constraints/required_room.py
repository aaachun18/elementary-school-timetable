from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment, RequiredRoomRule


class RequiredRoomConstraint(BaseConstraint):
    """H9 Required Room (Task 98, replaces H9 Room Type): when a
    ClassSubjectRequirement names a special room, the lesson must be held
    in exactly that room. No rule for a requirement means "原班上課" -- the
    class's homeroom, which this constraint does not check."""

    VIOLATION_TYPE = "H9_REQUIRED_ROOM"

    def __init__(self, rules: list[RequiredRoomRule]) -> None:
        self._room_by_requirement: dict[int, int] = {
            rule.class_subject_requirement_id: rule.room_id for rule in rules
        }

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for assignment in assignments:
            required_room_id = self._room_by_requirement.get(
                assignment.class_subject_requirement_id
            )
            if required_room_id is None or assignment.room_id == required_room_id:
                continue
            if assignment.room_id is None:
                # Not yet assigned a room -- nothing to compare yet.
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
                    class_subject_requirement_id=assignment.class_subject_requirement_id,
                    message=(
                        f"Lesson {assignment.lesson_id} must be held in room "
                        f"{required_room_id}, but is in room {assignment.room_id}."
                    ),
                    suggested_action=f"Move the lesson to room {required_room_id}.",
                )
            )
        return violations
