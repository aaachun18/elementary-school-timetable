from collections import defaultdict

from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment


class ClassConflictConstraint(BaseConstraint):
    """H2 Class Conflict: the same class cannot have two lessons at the
    same time_slot."""

    VIOLATION_TYPE = "H2_CLASS_CONFLICT"

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        by_class_slot: dict[tuple[int, int], list[LessonAssignment]] = (
            defaultdict(list)
        )
        for assignment in assignments:
            if assignment.time_slot_id is None:
                continue
            by_class_slot[
                (assignment.class_id, assignment.time_slot_id)
            ].append(assignment)

        violations: list[ConstraintViolation] = []
        for (class_id, time_slot_id), group in by_class_slot.items():
            if len(group) <= 1:
                continue
            for assignment in group:
                violations.append(
                    ConstraintViolation(
                        type=self.VIOLATION_TYPE,
                        severity=Severity.ERROR,
                        lesson_id=assignment.lesson_id,
                        teacher_id=assignment.teacher_id,
                        class_id=class_id,
                        subject_id=assignment.subject_id,
                        time_slot_id=time_slot_id,
                        message=(
                            f"Class {class_id} has {len(group)} lessons "
                            f"scheduled at time slot {time_slot_id}."
                        ),
                        suggested_action=(
                            "Move one of these lessons to a different time "
                            "slot."
                        ),
                    )
                )
        return violations
