from collections import defaultdict

from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment


class TeacherConflictConstraint(BaseConstraint):
    """H1 Teacher Conflict: the same teacher cannot be assigned to two
    lessons at the same time_slot."""

    VIOLATION_TYPE = "H1_TEACHER_CONFLICT"

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        by_teacher_slot: dict[tuple[int, int], list[LessonAssignment]] = (
            defaultdict(list)
        )
        for assignment in assignments:
            if assignment.teacher_id is None or assignment.time_slot_id is None:
                continue
            by_teacher_slot[
                (assignment.teacher_id, assignment.time_slot_id)
            ].append(assignment)

        violations: list[ConstraintViolation] = []
        for (teacher_id, time_slot_id), group in by_teacher_slot.items():
            if len(group) <= 1:
                continue
            for assignment in group:
                violations.append(
                    ConstraintViolation(
                        type=self.VIOLATION_TYPE,
                        severity=Severity.ERROR,
                        lesson_id=assignment.lesson_id,
                        teacher_id=teacher_id,
                        class_id=assignment.class_id,
                        subject_id=assignment.subject_id,
                        time_slot_id=time_slot_id,
                        message=(
                            f"Teacher {teacher_id} has {len(group)} lessons "
                            f"scheduled at time slot {time_slot_id}."
                        ),
                        suggested_action=(
                            "Move one of these lessons to a different time "
                            "slot, or assign a different teacher."
                        ),
                    )
                )
        return violations
