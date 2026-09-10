from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment, TimeSlotInfo


class NonTeachingPeriodConstraint(BaseConstraint):
    """H11 Non-teaching Period: a lesson cannot be scheduled into a time
    slot that isn't actually a teaching period (e.g. recess, lunch)."""

    VIOLATION_TYPE = "H11_NON_TEACHING_PERIOD"

    def __init__(self, time_slots: list[TimeSlotInfo]) -> None:
        self._is_teaching_period_by_slot: dict[int, bool] = {
            slot.time_slot_id: slot.is_teaching_period for slot in time_slots
        }

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for assignment in assignments:
            if assignment.time_slot_id is None:
                continue

            is_teaching_period = self._is_teaching_period_by_slot.get(
                assignment.time_slot_id
            )
            if is_teaching_period is None or is_teaching_period:
                # Unknown slot (nothing to check against) or genuinely a
                # teaching period -- either way, no violation.
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
                        f"Lesson {assignment.lesson_id} is scheduled at "
                        f"time slot {assignment.time_slot_id}, which is "
                        "not a teaching period."
                    ),
                    suggested_action="Move this lesson to a teaching period.",
                )
            )
        return violations
