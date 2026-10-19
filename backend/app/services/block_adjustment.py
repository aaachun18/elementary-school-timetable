"""Task 89: where every lesson goes when one lesson of a ScheduleVersion is
moved or swapped -- the whole lesson block (連堂) goes with it.

Pure functions over the version's rows as loaded once
(schedule_check.load_assignment_rows() + load_check_context()), no
database access: move-lesson / swap-lessons (preview and execution alike)
and move-candidates all call plan_move() / plan_swap(), so the three can
never disagree about which rows move where.

A "group" is what moves together: the Schedule rows of one block that are
in this version (in block order), or a lesson of no block on its own. A
block with only one lesson (the "1" of "2+1") behaves exactly like a lesson
of no block. Without blocks every plan is the single row the endpoints have
always changed, so nothing about them changes.

Rules (docs/SYSTEM_DESIGN.md, decision 26):
- Move: the dragged lesson is lesson k of its block; dropped on time slot
  T, the block starts k-1 periods before T, one lesson per period, all on
  T's weekday. Every period the whole block would take there must exist and
  be a teaching period (BLOCK_OUT_OF_RANGE), and no other lesson of the
  class may sit in a slot the moved lessons would take
  (BLOCK_TARGET_OCCUPIED -- that is a swap). Teacher and room stay.
- Swap: two groups of the same size exchange places -- lesson i of each
  goes to the time slot lesson i of the other is in; each keeps its teacher
  and room. With a block of two or more involved, both groups must be
  complete (every lesson of the block has a row with a time slot) and the
  same size, and not the same block (BLOCK_SWAP_UNSUPPORTED). Two groups of
  one lesson each swap exactly as two lessons always did.
- A fixed lesson does not stop anything: moving it off its fixed slot is
  reported by the check (FIXED_TIME_SLOT_MISMATCH), as for single lessons.

Task 92: placing a lesson that has no row in the version yet (place-lesson,
place-candidates) is planned here too, by plan_place() -- decision 28:
- The target must be a teaching period (NON_TEACHING_SLOT), for a single
  lesson as well.
- A lesson of a block is lesson k of it: the block starts k-1 periods
  before the target, exactly as for a move (BLOCK_OUT_OF_RANGE), and every
  lesson of the block that has no row yet is placed with it.
- Lessons of the block that already have a row must sit exactly where the
  block would put them; one elsewhere (or with no time slot) refuses the
  placement (BLOCK_PARTIAL_MISMATCH) -- nothing already placed is moved.
- No lesson of the class may sit in a slot a placed lesson would take
  (BLOCK_TARGET_OCCUPIED, a single lesson too): there is no swap for a
  lesson that isn't in the timetable.
"""

from dataclasses import dataclass, replace

from app.services import schedule_check

LessonAssignment = schedule_check.LessonAssignment

BLOCK_OUT_OF_RANGE = "BLOCK_OUT_OF_RANGE"
BLOCK_TARGET_OCCUPIED = "BLOCK_TARGET_OCCUPIED"
BLOCK_SWAP_UNSUPPORTED = "BLOCK_SWAP_UNSUPPORTED"
# Task 92: placement only (move-candidates has always reported this one
# for its own targets; services/move_candidates.py uses this constant).
NON_TEACHING_SLOT = "NON_TEACHING_SLOT"
BLOCK_PARTIAL_MISMATCH = "BLOCK_PARTIAL_MISMATCH"

REFUSAL_MESSAGES = {
    BLOCK_OUT_OF_RANGE: "連堂整組放不進這個位置，整組需要同一天相鄰的教學時段",
    BLOCK_TARGET_OCCUPIED: "連堂整組要佔用的時段已有本班的其他課，請改用對調",
    BLOCK_SWAP_UNSUPPORTED: "連堂只能與節數相同且已全部排課的另一組對調",
}


@dataclass(frozen=True)
class PlannedSlot:
    """One row of the plan: this Schedule row goes to this time slot."""

    schedule_id: int
    time_slot_id: int | None


@dataclass(frozen=True)
class Plan:
    """Exactly one of the two is set. `slots` lists every row that moves
    with the change (rows already in their target slot included), dragged
    group first; `refusal` is one of the codes above."""

    slots: tuple[PlannedSlot, ...] | None
    refusal: str | None


@dataclass(frozen=True)
class PlacedLesson:
    """Task 92: one lesson of a placement and the time slot it goes to."""

    lesson_id: int
    time_slot_id: int


@dataclass(frozen=True)
class Placement:
    """Task 92: exactly one of the two is set. `lessons` are the lessons
    that get a new row, in block order; `refusal` is NON_TEACHING_SLOT or
    one of the BLOCK_* codes."""

    lessons: tuple[PlacedLesson, ...] | None
    refusal: str | None


@dataclass(frozen=True)
class _Group:
    """The rows that move together, with each one's index in its block.
    size: how many lessons the block has (1 for a lesson of no block);
    complete: every lesson of the block has a row with a time slot."""

    key: tuple[int, int] | None  # (requirement, block_no), None for no block
    members: tuple[tuple[int, int], ...]  # (index in block, schedule_id)
    size: int
    complete: bool


class Layout:
    """The version's rows plus what plans need to know about time slots and
    blocks. Built once per request."""

    def __init__(
        self,
        rows: list[tuple[int, LessonAssignment]],
        context: schedule_check.CheckContext,
    ) -> None:
        resources = context.resources
        self.assignment = {schedule_id: assignment for schedule_id, assignment in rows}
        self._position = {
            position.time_slot_id: (position.weekday, position.period)
            for position in resources.time_slot_positions
        }
        teaching = {slot.time_slot_id: slot.is_teaching_period for slot in resources.time_slots}
        self._is_teaching = teaching
        self._teaching_slot_at = {
            place: slot_id
            for slot_id, place in self._position.items()
            if teaching.get(slot_id, True)
        }
        schedule_of_lesson = {assignment.lesson_id: schedule_id for schedule_id, assignment in rows}
        self._schedule_of_lesson = schedule_of_lesson
        self._group_of: dict[int, _Group] = {}
        self._block_of_lesson: dict[int, tuple[int, ...]] = {}
        for block in resources.lesson_blocks:
            if len(block.lesson_ids) < 2:
                continue  # a one-lesson block moves like any single lesson
            for lesson_id in block.lesson_ids:
                self._block_of_lesson[lesson_id] = block.lesson_ids
            members = tuple(
                (index, schedule_of_lesson[lesson_id])
                for index, lesson_id in enumerate(block.lesson_ids)
                if lesson_id in schedule_of_lesson
            )
            complete = len(members) == len(block.lesson_ids) and all(
                self.assignment[schedule_id].time_slot_id is not None for _, schedule_id in members
            )
            group = _Group(
                key=(block.class_subject_requirement_id, block.block_no),
                members=members,
                size=len(block.lesson_ids),
                complete=complete,
            )
            for _, schedule_id in members:
                self._group_of[schedule_id] = group

    def group(self, schedule_id: int) -> _Group:
        found = self._group_of.get(schedule_id)
        if found is not None:
            return found
        has_slot = self.assignment[schedule_id].time_slot_id is not None
        return _Group(key=None, members=((0, schedule_id),), size=1, complete=has_slot)

    def is_in_block(self, schedule_id: int) -> bool:
        return schedule_id in self._group_of

    def plan_move(self, schedule_id: int, target_time_slot_id: int) -> Plan:
        group = self.group(schedule_id)
        if group.key is None:
            return Plan(slots=(PlannedSlot(schedule_id, target_time_slot_id),), refusal=None)

        place = self._position.get(target_time_slot_id)
        if place is None:
            return Plan(slots=None, refusal=BLOCK_OUT_OF_RANGE)
        weekday, period = place
        dragged_index = next(index for index, member in group.members if member == schedule_id)
        start = period - dragged_index
        span = [self._teaching_slot_at.get((weekday, start + index)) for index in range(group.size)]
        if any(slot_id is None for slot_id in span):
            return Plan(slots=None, refusal=BLOCK_OUT_OF_RANGE)

        targets = {member: span[index] for index, member in group.members}
        moving = set(targets)
        class_id = self.assignment[schedule_id].class_id
        taken = set(targets.values())
        for other_id, other in self.assignment.items():
            if other_id not in moving and other.class_id == class_id and other.time_slot_id in taken:
                return Plan(slots=None, refusal=BLOCK_TARGET_OCCUPIED)
        return Plan(
            slots=tuple(PlannedSlot(member, targets[member]) for _, member in group.members),
            refusal=None,
        )

    def plan_swap(self, schedule_id: int, other_schedule_id: int) -> Plan:
        first, second = self.group(schedule_id), self.group(other_schedule_id)
        if first.key is None and second.key is None:
            return Plan(
                slots=(
                    PlannedSlot(schedule_id, self.assignment[other_schedule_id].time_slot_id),
                    PlannedSlot(other_schedule_id, self.assignment[schedule_id].time_slot_id),
                ),
                refusal=None,
            )
        if (
            first.key == second.key
            or first.size != second.size
            or not first.complete
            or not second.complete
        ):
            return Plan(slots=None, refusal=BLOCK_SWAP_UNSUPPORTED)
        slot_of = {schedule_id: self.assignment[schedule_id].time_slot_id for schedule_id in self.assignment}
        planned = [
            PlannedSlot(mine, slot_of[theirs])
            for (_, mine), (_, theirs) in zip(first.members, second.members)
        ] + [
            PlannedSlot(theirs, slot_of[mine])
            for (_, mine), (_, theirs) in zip(first.members, second.members)
        ]
        return Plan(slots=tuple(planned), refusal=None)


    def is_lesson_in_block(self, lesson_id: int) -> bool:
        """Task 92: by lesson, for a lesson that may have no row."""
        return lesson_id in self._block_of_lesson

    def plan_place(self, lesson_id: int, class_id: int, target_time_slot_id: int) -> Placement:
        """Task 92: where `lesson_id` (no row in this version, of class
        `class_id`) and the unplaced rest of its block go when it is put
        in the target slot -- see the module docstring for the rules."""
        place = self._position.get(target_time_slot_id)
        if place is None or not self._is_teaching.get(target_time_slot_id, True):
            return Placement(lessons=None, refusal=NON_TEACHING_SLOT)
        weekday, period = place

        block = self._block_of_lesson.get(lesson_id, (lesson_id,))
        start = period - block.index(lesson_id)
        span = [self._teaching_slot_at.get((weekday, start + index)) for index in range(len(block))]
        if any(slot_id is None for slot_id in span):
            return Placement(lessons=None, refusal=BLOCK_OUT_OF_RANGE)

        placed: list[PlacedLesson] = []
        for member, slot_id in zip(block, span):
            assert slot_id is not None
            schedule_id = self._schedule_of_lesson.get(member)
            if schedule_id is None:
                placed.append(PlacedLesson(member, slot_id))
            elif self.assignment[schedule_id].time_slot_id != slot_id:
                return Placement(lessons=None, refusal=BLOCK_PARTIAL_MISMATCH)

        taken = {item.time_slot_id for item in placed}
        for other in self.assignment.values():
            if other.class_id == class_id and other.time_slot_id in taken:
                return Placement(lessons=None, refusal=BLOCK_TARGET_OCCUPIED)
        return Placement(lessons=tuple(placed), refusal=None)


def arranged(rows: list[tuple[int, LessonAssignment]], plan: Plan) -> list[LessonAssignment]:
    """The version's assignments after `plan` (rooms unchanged), in the
    order of `rows` -- what check_assignments() is run on."""
    assert plan.slots is not None
    new_slot = {planned.schedule_id: planned.time_slot_id for planned in plan.slots}
    return [
        replace(assignment, time_slot_id=new_slot[schedule_id]) if schedule_id in new_slot else assignment
        for schedule_id, assignment in rows
    ]
