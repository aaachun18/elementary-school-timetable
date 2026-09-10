from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment, RequiredTeacherRule


class RequiredTeacherConstraint(BaseConstraint):
    """H6 Required Teacher: when a ClassSubjectRequirement specifies a
    required teacher, its lessons must be taught by exactly that teacher.

    Constructed with the rule list up front (same reasoning as H4/H5): this
    data doesn't come from the assignments being checked, and a requirement
    with no rule in the list is simply unconstrained (see
    RequiredTeacherRule's docstring for why it's a sparse list rather than
    an Optional field).
    """

    VIOLATION_TYPE = "H6_REQUIRED_TEACHER"

    def __init__(self, rules: list[RequiredTeacherRule]) -> None:
        self._required_teacher_by_requirement: dict[int, int] = {
            rule.class_subject_requirement_id: rule.required_teacher_id
            for rule in rules
        }

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for assignment in assignments:
            if assignment.teacher_id is None:
                continue

            required_teacher_id = self._required_teacher_by_requirement.get(
                assignment.class_subject_requirement_id
            )
            if required_teacher_id is None:
                # No rule for this requirement -> no restriction.
                continue
            if assignment.teacher_id == required_teacher_id:
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
                        f"Lesson {assignment.lesson_id} requires teacher "
                        f"{required_teacher_id}, but teacher "
                        f"{assignment.teacher_id} is assigned instead."
                    ),
                    suggested_action=(
                        f"Assign teacher {required_teacher_id} to this "
                        "lesson."
                    ),
                )
            )
        return violations
