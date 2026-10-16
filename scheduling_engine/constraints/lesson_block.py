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
      day in adjacent teaching periods in block order (a missing period or a
      non-teaching period such as lunch anywhere in the block's span breaks
      it), or don't share one teacher and one room.
    - BLOCK_SAME_DAY: two different blocks of one requirement have lessons
      on the same day.

    Not one of AGENTS.md's H1-H12 (a rule of its own, like the fixed time
    slot). The search builds every block from a window of consecutive
    periods, so there only BLOCK_SAME_DAY can actually trigger. Task 88:
    the schedule check (backend services/schedule_check.py) runs this same
    class over stored timetables, so the rule is written once.

    A block placed only in part (Task 88): its lessons that have a time
    slot are judged, each at the period its place in the block calls for,
    and the whole block's span (every period the complete block would take
    there) must be teaching periods -- so a partly placed block is flagged
    exactly when no way of placing the rest could make it right, never
    merely for being incomplete. The missing lessons themselves are H7's
    (no Schedule row) or INCOMPLETE_SCHEDULE_ROW's (a row without a time
    slot) business, the same split every other rule uses. A lesson without a teacher is left
    out of the "one teacher" comparison for the same reason. A time slot
    with no position is not judged.
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
        teaching = {slot.time_slot_id: slot.is_teaching_period for slot in time_slots}
        # (weekday, period) -> is it a teaching period. A slot without a
        # TimeSlotInfo counts as teaching (same stance as H11); a period
        # with no slot at all is simply absent.
        self._teaching_at = {
            (position.weekday, position.period): teaching.get(position.time_slot_id, True)
            for position in time_slot_positions
        }

    @staticmethod
    def identity_key(violation_type: str, requirement_id: int, block_nos: list[int]) -> str:
        """Which block(s) the problem is about -- no time slot, no weekday,
        no lesson -- so the same problem keeps its key across a move."""
        return f"{violation_type}:{requirement_id}:{','.join(str(no) for no in sorted(block_nos))}"

    def _violation(
        self,
        violation_type: str,
        assignment: LessonAssignment,
        block_no: int,
        key: str,
        message: str,
        action: str,
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
            block_no=block_no,
            identity_key=key,
        )

    def _placed_members(
        self, assignments: list[LessonAssignment]
    ) -> dict[tuple[int, int], list[tuple[int, LessonAssignment]]]:
        """(requirement, block_no) -> [(index in block, assignment)] of the
        block lessons that have a time slot with a known position, in block
        order."""
        placed: dict[tuple[int, int], list[tuple[int, LessonAssignment]]] = {}
        for assignment in assignments:
            entry = self._block_of.get(assignment.lesson_id)
            if entry is None or assignment.time_slot_id not in self._position:
                continue
            block, index = entry
            placed.setdefault((block.class_subject_requirement_id, block.block_no), []).append(
                (index, assignment)
            )
        for members in placed.values():
            members.sort(key=lambda item: item[0])
        return placed

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        if not self._blocks:
            return []
        placed = self._placed_members(assignments)

        violations: list[ConstraintViolation] = []
        # requirement -> weekday -> block_no -> that block's lessons that day
        by_day: dict[int, dict[int, dict[int, list[LessonAssignment]]]] = {}
        size_of = {
            (block.class_subject_requirement_id, block.block_no): len(block.lesson_ids)
            for block in self._blocks
        }
        for (requirement_id, block_no), members in sorted(placed.items()):
            if not self.is_consecutive(members, size_of[(requirement_id, block_no)]):
                key = self.identity_key(self.NOT_CONSECUTIVE, requirement_id, [block_no])
                for _, assignment in members:
                    violations.append(
                        self._violation(
                            self.NOT_CONSECUTIVE,
                            assignment,
                            block_no,
                            key,
                            f"Block {block_no} of requirement {requirement_id} is not taught "
                            "on one day in adjacent teaching periods by one teacher in one room.",
                            "Place the whole block in consecutive teaching periods of one day.",
                        )
                    )
            for _, assignment in members:
                weekday = self._position[assignment.time_slot_id].weekday  # type: ignore[index]
                by_day.setdefault(requirement_id, {}).setdefault(weekday, {}).setdefault(
                    block_no, []
                ).append(assignment)

        for requirement_id, blocks_by_day in sorted(by_day.items()):
            for weekday, lessons_by_block in sorted(blocks_by_day.items()):
                if len(lessons_by_block) < 2:
                    continue
                block_nos = sorted(lessons_by_block)
                key = self.identity_key(self.SAME_DAY, requirement_id, block_nos)
                for block_no in block_nos:
                    for assignment in lessons_by_block[block_no]:
                        violations.append(
                            self._violation(
                                self.SAME_DAY,
                                assignment,
                                block_no,
                                key,
                                f"Blocks {block_nos} of requirement {requirement_id} "
                                f"are all on weekday {weekday}.",
                                "Move one of these blocks to another day.",
                            )
                        )
        return violations

    def is_consecutive(self, members: list[tuple[int, LessonAssignment]], size: int) -> bool:
        """`members`: (index in block, assignment) of one block's placed
        lessons, in block order, every one with a known position; `size`:
        how many lessons the block has. True if they can all be part of one
        correct placement of the block."""
        first_index, first = members[0]
        start = self._position[first.time_slot_id]  # type: ignore[index]
        weekday = start.weekday
        # The period the block's lesson 0 would be in.
        base_period = start.period - first_index
        for index, assignment in members:
            position = self._position[assignment.time_slot_id]  # type: ignore[index]
            if position.weekday != weekday or position.period != base_period + index:
                return False
        for period in range(base_period, base_period + size):
            if not self._teaching_at.get((weekday, period), False):
                return False
        teachers = {assignment.teacher_id for _, assignment in members if assignment.teacher_id is not None}
        rooms = {assignment.room_id for _, assignment in members}
        return len(teachers) <= 1 and len(rooms) <= 1
