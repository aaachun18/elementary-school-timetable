from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import ClassAllowedTimeSlots, LessonAssignment


class ClassTimeSlotConstraint(BaseConstraint):
    """H13 Grade Time Slots (Task 98): a class may only be scheduled in the
    time slots its grade is open for in the semester (e.g. 低年級 has no
    lessons after period 5 except on Tuesday). A class with no
    ClassAllowedTimeSlots entry is not restricted."""

    VIOLATION_TYPE = "H13_CLASS_TIME_SLOT"

    def __init__(self, allowed: list[ClassAllowedTimeSlots]) -> None:
        self._allowed_by_class: dict[int, frozenset[int]] = {
            item.class_id: item.time_slot_ids for item in allowed
        }

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for assignment in assignments:
            if assignment.time_slot_id is None:
                continue
            allowed = self._allowed_by_class.get(assignment.class_id)
            if allowed is None or assignment.time_slot_id in allowed:
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
                        f"Lesson {assignment.lesson_id} of class {assignment.class_id} "
                        f"is in time slot {assignment.time_slot_id}, which its grade "
                        "is not open for."
                    ),
                    suggested_action=(
                        "Move the lesson to a time slot the grade is open for, or "
                        "open this time slot for the grade."
                    ),
                )
            )
        return violations
