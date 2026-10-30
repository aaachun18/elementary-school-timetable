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

Rules (docs/SYSTEM_DESIGN.md, decision 26; since 2026-10-30 a block may go
anywhere it fits):
- Move: the dragged lesson is lesson k of its block; dropped on time slot
  T, the block starts k-1 periods before T, one lesson per period, all on
  T's weekday. Every period the whole block would take there must exist and
  be a teaching period (BLOCK_OUT_OF_RANGE). The class's other lessons in
  those periods make room: each of them (with its whole block) goes to the
  periods the block leaves -- a block of them into consecutive ones, single
  lessons into the rest in period order. When they don't fit there, the
  move is refused (BLOCK_DISPLACED_UNFIT). Teacher and room stay.
- Swap: two lessons of no block exchange time slots, and so do two complete
  blocks of the same size (lesson i of each goes to the time slot lesson i
  of the other is in). Any other swap with a block involved is the move
  above: the block (the dragged one; else the one dropped on) moves so that
  its lesson lands where the other one is, and the other one -- with
  whatever else of the class is in the way -- goes to the periods it
  leaves. Each row keeps its teacher and room.
- A fixed lesson does not stop anything: moving it off its fixed slot is
  reported by the check (FIXED_TIME_SLOT_MISMATCH), as for single lessons.
- 共同排課: every planned row takes the other members' rows of its 合併節
  (the lessons that sit in the same slot with it) to the same slot -- a
  combined lesson always moves as one. A clash this causes for another
  member's class is reported by the check (H2), not refused.

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
BLOCK_DISPLACED_UNFIT = "BLOCK_DISPLACED_UNFIT"
# Task 92: placement only (move-candidates has always reported this one
# for its own targets; services/move_candidates.py uses this constant).
NON_TEACHING_SLOT = "NON_TEACHING_SLOT"
BLOCK_PARTIAL_MISMATCH = "BLOCK_PARTIAL_MISMATCH"

REFUSAL_MESSAGES = {
    BLOCK_OUT_OF_RANGE: "連堂整組放不進這個位置，整組需要同一天相鄰的教學時段",
    BLOCK_TARGET_OCCUPIED: "要放入的時段已有本班的其他課",
    BLOCK_DISPLACED_UNFIT: "被換走的課放不進連堂空出來的時段",
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
    group first; `refusal` is one of the codes above. `displaced`: the rows
    among `slots` that only make room for a block (a move's target room is
    not theirs)."""

    slots: tuple[PlannedSlot, ...] | None
    refusal: str | None
    displaced: frozenset[int] = frozenset()


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
        # 共同排課: lesson -> the other members' lessons of its 合併節 that
        # share its slot.
        self._partners: dict[int, list[int]] = {}
        for combined in resources.combined_lessons:
            for index in range(min(len(ids) for ids in combined.member_lesson_ids)):
                same_slot = [ids[index] for ids in combined.member_lesson_ids]
                for lesson_id in same_slot:
                    self._partners[lesson_id] = [other for other in same_slot if other != lesson_id]
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

    def partner_rows(self, schedule_id: int) -> list[int]:
        """共同排課: the rows of the other members' lessons that share this
        row's slot (none for a lesson of no combined lesson)."""
        lesson_id = self.assignment[schedule_id].lesson_id
        return [
            self._schedule_of_lesson[partner]
            for partner in self._partners.get(lesson_id, [])
            if partner in self._schedule_of_lesson
        ]

    def with_partner_rows(self, schedule_ids: list[int]) -> list[int]:
        """The rows plus their partners (partner_rows()), each once, in id
        order."""
        rows = set(schedule_ids)
        for schedule_id in schedule_ids:
            rows.update(self.partner_rows(schedule_id))
        return sorted(rows)

    def _with_partners(self, plan: Plan) -> Plan:
        """Every planned row's partners go to the same slot with it."""
        if plan.slots is None or not self._partners:
            return plan
        planned = list(plan.slots)
        seen = {item.schedule_id for item in planned}
        for item in plan.slots:
            for partner in self.partner_rows(item.schedule_id):
                if partner not in seen:
                    seen.add(partner)
                    planned.append(PlannedSlot(partner, item.time_slot_id))
        return Plan(slots=tuple(planned), refusal=None, displaced=plan.displaced)

    def plan_move(self, schedule_id: int, target_time_slot_id: int) -> Plan:
        return self._with_partners(self._plan_move(schedule_id, target_time_slot_id))

    def plan_swap(self, schedule_id: int, other_schedule_id: int) -> Plan:
        if other_schedule_id in self.partner_rows(schedule_id):
            # Two members of one 合併節 already share their slot.
            return Plan(slots=(), refusal=None)
        return self._with_partners(self._plan_swap(schedule_id, other_schedule_id))

    def _plan_move(self, schedule_id: int, target_time_slot_id: int) -> Plan:
        if self.group(schedule_id).key is None:
            return Plan(slots=(PlannedSlot(schedule_id, target_time_slot_id),), refusal=None)
        return self._plan_block_to(schedule_id, target_time_slot_id)

    def _rows_of_group(self, schedule_id: int) -> list[int]:
        return [member for _, member in self.group(schedule_id).members]

    def _slot_order(self, time_slot_id: int) -> tuple[int, int]:
        return self._position.get(time_slot_id, (0, 0))

    def _plan_block_to(
        self, schedule_id: int, target_time_slot_id: int | None, also_displaced: int | None = None
    ) -> Plan:
        """The block of `schedule_id` moves so that this lesson lands in the
        target slot; the class's lessons in its way (and `also_displaced`'s
        group, for a swap) go to the periods it leaves (see the module
        docstring)."""
        group = self.group(schedule_id)
        place = None if target_time_slot_id is None else self._position.get(target_time_slot_id)
        if place is None:
            return Plan(slots=None, refusal=BLOCK_OUT_OF_RANGE)
        weekday, period = place
        dragged_index = next(index for index, member in group.members if member == schedule_id)
        start = period - dragged_index
        span = [self._teaching_slot_at.get((weekday, start + index)) for index in range(group.size)]
        if any(slot_id is None for slot_id in span):
            return Plan(slots=None, refusal=BLOCK_OUT_OF_RANGE)

        targets = {member: span[index] for index, member in group.members}
        window = set(targets.values())
        class_id = self.assignment[schedule_id].class_id
        seen = set(targets)
        displaced: list[int] = []

        def displace(row_id: int) -> None:
            for member in self._rows_of_group(row_id):
                if member not in seen:
                    seen.add(member)
                    displaced.append(member)

        for other_id in sorted(self.assignment):
            other = self.assignment[other_id]
            if other_id not in seen and other.class_id == class_id and other.time_slot_id in window:
                displace(other_id)
        if also_displaced is not None:
            displace(also_displaced)

        old_slots = {self.assignment[member].time_slot_id for member in targets}
        left = sorted(
            (slot_id for slot_id in old_slots if slot_id is not None and slot_id not in window),
            key=self._slot_order,
        )
        fitted = self._fit_displaced(displaced, left)
        if fitted is None:
            return Plan(slots=None, refusal=BLOCK_DISPLACED_UNFIT)
        return Plan(
            slots=tuple(PlannedSlot(member, targets[member]) for _, member in group.members)
            + tuple(PlannedSlot(row_id, slot_id) for row_id, slot_id in fitted),
            refusal=None,
            displaced=frozenset(row_id for row_id, _ in fitted),
        )

    def _fit_displaced(self, displaced: list[int], free: list[int]) -> list[tuple[int, int]] | None:
        """Where each displaced row goes among the `free` slots (in period
        order): every displaced block into consecutive periods of one day
        (longest first), then the single lessons in order. None when they
        don't fit."""
        groups: list[list[int]] = []
        grouped: set[int] = set()
        for row_id in displaced:
            if row_id in grouped:
                continue
            members = [member for member in self._rows_of_group(row_id) if member in displaced]
            grouped.update(members)
            groups.append(members)
        remaining = list(free)
        fitted: list[tuple[int, int]] = []
        for members in sorted((g for g in groups if len(g) > 1), key=len, reverse=True):
            run = self._consecutive_run(remaining, len(members))
            if run is None:
                return None
            for member, slot_id in zip(members, run, strict=True):
                fitted.append((member, slot_id))
                remaining.remove(slot_id)
        for members in groups:
            if len(members) > 1:
                continue
            if not remaining:
                return None
            fitted.append((members[0], remaining.pop(0)))
        return fitted

    def _consecutive_run(self, free: list[int], size: int) -> list[int] | None:
        """The first `size` slots in a row of `free` that are consecutive
        periods of one day, or None."""
        for start in range(len(free) - size + 1):
            run = free[start : start + size]
            places = [self._slot_order(slot_id) for slot_id in run]
            weekday, period = places[0]
            if all(place == (weekday, period + index) for index, place in enumerate(places)):
                return run
        return None

    def _plan_swap(self, schedule_id: int, other_schedule_id: int) -> Plan:
        first, second = self.group(schedule_id), self.group(other_schedule_id)
        slot_of = {row_id: assignment.time_slot_id for row_id, assignment in self.assignment.items()}
        if first.key is None and second.key is None:
            return Plan(
                slots=(
                    PlannedSlot(schedule_id, slot_of[other_schedule_id]),
                    PlannedSlot(other_schedule_id, slot_of[schedule_id]),
                ),
                refusal=None,
            )
        if (
            first.key is not None
            and second.key is not None
            and first.key != second.key
            and first.size == second.size
            and first.complete
            and second.complete
        ):
            planned = [
                PlannedSlot(mine, slot_of[theirs])
                for (_, mine), (_, theirs) in zip(first.members, second.members)
            ] + [
                PlannedSlot(theirs, slot_of[mine])
                for (_, mine), (_, theirs) in zip(first.members, second.members)
            ]
            return Plan(slots=tuple(planned), refusal=None)
        if first.key is not None:
            # The dragged block moves onto the other lesson (two lessons of
            # one block: the block shifts).
            also = None if first.key == second.key else other_schedule_id
            return self._plan_block_to(schedule_id, slot_of[other_schedule_id], also)
        # A single lesson dropped on a block: the block comes to it -- the
        # lesson dropped on landing in its slot, else (that runs off the
        # day) the first other lesson of the block that fits.
        anchors = [other_schedule_id] + [
            member for member in self._rows_of_group(other_schedule_id) if member != other_schedule_id
        ]
        plan = Plan(slots=None, refusal=BLOCK_OUT_OF_RANGE)
        for anchor in anchors:
            plan = self._plan_block_to(anchor, slot_of[schedule_id], schedule_id)
            if plan.slots is not None:
                break
        if plan.slots is None:
            return plan
        mine = [item for item in plan.slots if item.schedule_id == schedule_id]
        rest = [item for item in plan.slots if item.schedule_id != schedule_id]
        return Plan(slots=tuple(mine + rest), refusal=None, displaced=plan.displaced)

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
