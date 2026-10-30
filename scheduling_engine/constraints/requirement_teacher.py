from collections import defaultdict

from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment


class RequirementSingleTeacherConstraint(BaseConstraint):
    """H15 One Teacher per Course: every lesson of one requirement (one
    class's one subject, e.g. 六年甲班的國際視野) is taught by the same
    teacher -- with no required teacher (H6) the scheduler may pick anyone,
    but only one person for the whole course.

    Lessons without a teacher are not checked (an unplaced lesson can't
    conflict with anything)."""

    VIOLATION_TYPE = "H15_REQUIREMENT_MIXED_TEACHERS"

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        by_requirement: dict[int, list[LessonAssignment]] = defaultdict(list)
        for assignment in assignments:
            if assignment.teacher_id is not None:
                by_requirement[assignment.class_subject_requirement_id].append(assignment)

        violations: list[ConstraintViolation] = []
        for requirement_id, group in by_requirement.items():
            teacher_ids = sorted({assignment.teacher_id for assignment in group if assignment.teacher_id is not None})
            if len(teacher_ids) <= 1:
                continue
            for assignment in group:
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
                        class_subject_requirement_id=requirement_id,
                        message=(
                            f"Requirement {requirement_id} is taught by "
                            f"{len(teacher_ids)} teachers ({teacher_ids}); "
                            "all of its lessons need the same teacher."
                        ),
                        suggested_action="Give every lesson of this course the same teacher (換教師).",
                        identity_key=f"{self.VIOLATION_TYPE}:{requirement_id}",
                    )
                )
        return violations
