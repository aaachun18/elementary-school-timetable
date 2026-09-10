from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment, TeacherUnavailability


class TeacherAvailabilityConstraint(BaseConstraint):
    """H4 Teacher Availability: a teacher cannot be assigned to a
    time_slot they've been marked unavailable for.

    Unlike H1-H3, this constraint needs data beyond the assignments being
    checked (the unavailability list), so it's constructed with that data
    up front rather than taking it as a validate()/explain_violations()
    argument -- the same instance can then be reused to check many
    candidate schedules against the same fixed unavailability data (e.g.
    during Greedy/Backtracking search, a later Task) without re-passing it
    every call.
    """

    VIOLATION_TYPE = "H4_TEACHER_AVAILABILITY"

    def __init__(self, unavailability: list[TeacherUnavailability]) -> None:
        self._unavailable_pairs = {
            (entry.teacher_id, entry.time_slot_id) for entry in unavailability
        }

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for assignment in assignments:
            if assignment.teacher_id is None or assignment.time_slot_id is None:
                continue
            if (
                assignment.teacher_id,
                assignment.time_slot_id,
            ) not in self._unavailable_pairs:
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
                    message=(
                        f"Teacher {assignment.teacher_id} is marked "
                        f"unavailable at time slot {assignment.time_slot_id}."
                    ),
                    suggested_action=(
                        "Assign a different teacher or move this lesson to "
                        "a time slot the teacher is available for."
                    ),
                )
            )
        return violations
