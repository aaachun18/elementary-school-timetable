from collections import defaultdict

from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment, RoomCapacity, occupancy_key


class RoomConflictConstraint(BaseConstraint):
    """H3 Room Conflict: a room cannot host more lessons at the same
    time_slot than the classes it holds at once (RoomCapacity, 1 by
    default). The lessons of one 合併節 (共同排課) count once. room_id is
    Optional on LessonAssignment (not every lesson needs a specific room);
    assignments with room_id=None don't participate in this check at all --
    there is nothing to conflict over."""

    VIOLATION_TYPE = "H3_ROOM_CONFLICT"

    def __init__(
        self,
        capacities: list[RoomCapacity] | None = None,
        joint_keys: dict[int, str] | None = None,
    ) -> None:
        self._capacity = {item.room_id: item.max_classes for item in capacities or []}
        self._joint_keys = joint_keys or {}

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
            uses = len({occupancy_key(assignment, self._joint_keys) for assignment in group})
            if uses <= self._capacity.get(room_id, 1):
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
                            f"Room {room_id} has {uses} lessons "
                            f"scheduled at time slot {time_slot_id}, more than "
                            f"the {self._capacity.get(room_id, 1)} it holds."
                        ),
                        suggested_action=(
                            "Move one of these lessons to a different room "
                            "or time slot."
                        ),
                    )
                )
        return violations
