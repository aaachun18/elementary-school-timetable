from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment, TeacherQualification


class TeacherQualificationConstraint(BaseConstraint):
    """H5 Teacher Qualification: a teacher must hold a qualification for
    the subject they're assigned to teach.

    Constructed with the qualification list up front, for the same reason
    as TeacherAvailabilityConstraint (see its docstring): this data doesn't
    come from the assignments being checked, and the same instance can be
    reused across many candidate schedules during search.
    """

    VIOLATION_TYPE = "H5_TEACHER_QUALIFICATION"

    def __init__(self, qualifications: list[TeacherQualification]) -> None:
        self._qualified_pairs = {
            (entry.teacher_id, entry.subject_id) for entry in qualifications
        }

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for assignment in assignments:
            if assignment.teacher_id is None:
                # No teacher assigned yet -- nothing to be unqualified for.
                continue
            if (
                assignment.teacher_id,
                assignment.subject_id,
            ) in self._qualified_pairs:
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
                        f"Teacher {assignment.teacher_id} is not qualified "
                        f"to teach subject {assignment.subject_id}."
                    ),
                    suggested_action=(
                        "Assign a teacher who holds a qualification for "
                        "this subject."
                    ),
                )
            )
        return violations
