from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import (
    LessonAssignment,
    LessonBlock,
    TimeSlotInfo,
    TimeSlotPosition,
)


class LessonBlockConstraint(BaseConstraint):
    """Task 87: lesson blocks (連堂, from a requirement's lesson_pattern).

    - BLOCK_NOT_CONSECUTIVE: the placed lessons of one block are not on one
      day in adjacent teaching periods in block order, or don't share one
      teacher and one room.
    - BLOCK_SAME_DAY: two different blocks of one requirement are on the
      same day.

    Not one of AGENTS.md's H1-H12 (a rule of its own, like the fixed time
    slot). The search builds every block from a window of consecutive
    periods, so there only BLOCK_SAME_DAY can actually trigger; the full
    check is here so the same rule can judge a stored timetable later.
    Only lessons that are in a block and placed (teacher and time slot set)
    are looked at; a time slot with no position is not judged.
    """

    NOT_CONSECUTIVE = "BLOCK_NOT_CONSECUTIVE"
    SAME_DAY = "BLOCK_SAME_DAY"

    def __init__(
        self,
        lesson_blocks: list[LessonBlock],
        time_slot_positions: list[TimeSlotPosition],
        time_slots: list[TimeSlotInfo],
    ) -> None:
        self._blocks = lesson_blocks
        self._block_of: dict[int, tuple[LessonBlock, int]] = {}
        for block in lesson_blocks:
            for index, lesson_id in enumerate(block.lesson_ids):
                self._block_of[lesson_id] = (block, index)
        self._position = {position.time_slot_id: position for position in time_slot_positions}
        self._teaching = {slot.time_slot_id: slot.is_teaching_period for slot in time_slots}

    def _violation(
        self, violation_type: str, assignment: LessonAssignment, message: str, action: str
    ) -> ConstraintViolation:
        return ConstraintViolation(
            type=violation_type,
            severity=Severity.ERROR,
            lesson_id=assignment.lesson_id,
            teacher_id=assignment.teacher_id,
            class_id=assignment.class_id,
            subject_id=assignment.subject_id,
            time_slot_id=assignment.time_slot_id,
            room_id=assignment.room_id,
            class_subject_requirement_id=assignment.class_subject_requirement_id,
            message=message,
            suggested_action=action,
        )

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        if not self._blocks:
            return []
        placed: dict[tuple[int, int], list[tuple[int, LessonAssignment]]] = {}
        for assignment in assignments:
            entry = self._block_of.get(assignment.lesson_id)
            if entry is None or assignment.time_slot_id is None:
                continue
            if assignment.time_slot_id not in self._position:
                continue
            block, index = entry
            placed.setdefault((block.class_subject_requirement_id, block.block_no), []).append(
                (index, assignment)
            )

        violations: list[ConstraintViolation] = []
        weekdays_by_requirement: dict[int, dict[int, list[int]]] = {}
        for (requirement_id, block_no), members in placed.items():
            members.sort(key=lambda item: item[0])
            if not self._is_consecutive(members):
                for _, assignment in members:
                    violations.append(
                        self._violation(
                            self.NOT_CONSECUTIVE,
                            assignment,
                            f"Block {block_no} of requirement {requirement_id} is not taught "
                            "on one day in adjacent teaching periods by one teacher in one room.",
                            "Place the whole block in consecutive teaching periods of one day.",
                        )
                    )
            weekday = self._position[members[0][1].time_slot_id].weekday  # type: ignore[index]
            weekdays_by_requirement.setdefault(requirement_id, {}).setdefault(weekday, []).append(block_no)

        for requirement_id, blocks_by_day in weekdays_by_requirement.items():
            for weekday, block_nos in blocks_by_day.items():
                if len(block_nos) < 2:
                    continue
                for block_no in block_nos:
                    for _, assignment in placed[(requirement_id, block_no)]:
                        violations.append(
                            self._violation(
                                self.SAME_DAY,
                                assignment,
                                f"Blocks {sorted(block_nos)} of requirement {requirement_id} "
                                f"are all on weekday {weekday}.",
                                "Move one of these blocks to another day.",
                            )
                        )
        return violations

    def _is_consecutive(self, members: list[tuple[int, LessonAssignment]]) -> bool:
        first = members[0][1]
        start = self._position[first.time_slot_id]  # type: ignore[index]
        for index, assignment in members:
            position = self._position[assignment.time_slot_id]  # type: ignore[index]
            if (
                position.weekday != start.weekday
                or position.period != start.period + (index - members[0][0])
                or not self._teaching.get(assignment.time_slot_id, True)  # type: ignore[arg-type]
                or assignment.teacher_id != first.teacher_id
                or assignment.room_id != first.room_id
            ):
                return False
        return True
