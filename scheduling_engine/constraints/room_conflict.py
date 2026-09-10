from collections import defaultdict

from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment


class RoomConflictConstraint(BaseConstraint):
    """H3 Room Conflict: the same room cannot host two lessons at the same
    time_slot. room_id is Optional on LessonAssignment (not every lesson
    needs a specific room); assignments with room_id=None don't participate
    in this check at all -- there is nothing to conflict over."""

    VIOLATION_TYPE = "H3_ROOM_CONFLICT"

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        by_room_slot: dict[tuple[int, int], list[LessonAssignment]] = defaultdict(
            list
        )
        for assignment in assignments:
            if assignment.room_id is None or assignment.time_slot_id is None:
                continue
            by_room_slot[(assignment.room_id, assignment.time_slot_id)].append(
                assignment
            )

        violations: list[ConstraintViolation] = []
        for (room_id, time_slot_id), group in by_room_slot.items():
            if len(group) <= 1:
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
                        time_slot_id=time_slot_id,
                        room_id=room_id,
                        message=(
                            f"Room {room_id} has {len(group)} lessons "
                            f"scheduled at time slot {time_slot_id}."
                        ),
                        suggested_action=(
                            "Move one of these lessons to a different room "
                            "or time slot."
                        ),
                    )
                )
        return violations
