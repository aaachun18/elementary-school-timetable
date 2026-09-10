from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import ActiveStatusInfo, LessonAssignment


class ActiveStatusConstraint(BaseConstraint):
    """H12 Active Status: a lesson cannot involve a disabled teacher,
    class, subject, or room. class_id/subject_id are always checked (they
    are never None on a LessonAssignment); teacher_id/room_id are only
    checked when actually assigned -- an unassigned slot can't be
    "disabled", it's just not filled in yet."""

    VIOLATION_TYPE = "H12_ACTIVE_STATUS"

    def __init__(self, active_statuses: list[ActiveStatusInfo]) -> None:
        self._inactive: set[tuple[str, int]] = {
            (info.entity_type, info.entity_id)
            for info in active_statuses
            if not info.is_active
        }

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for assignment in assignments:
            inactive_entities: list[str] = []

            if assignment.teacher_id is not None and (
                "teacher",
                assignment.teacher_id,
            ) in self._inactive:
                inactive_entities.append(f"teacher {assignment.teacher_id}")

            if ("class", assignment.class_id) in self._inactive:
                inactive_entities.append(f"class {assignment.class_id}")

            if ("subject", assignment.subject_id) in self._inactive:
                inactive_entities.append(f"subject {assignment.subject_id}")

            if assignment.room_id is not None and (
                "room",
                assignment.room_id,
            ) in self._inactive:
                inactive_entities.append(f"room {assignment.room_id}")

            if not inactive_entities:
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
                        f"Lesson {assignment.lesson_id} involves inactive "
                        f"entities: {', '.join(inactive_entities)}."
                    ),
                    suggested_action=(
                        "Reactivate the affected entity, or reassign this "
                        "lesson to an active teacher/class/subject/room."
                    ),
                )
            )
        return violations
