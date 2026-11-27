"""Task 87: lesson blocks (連堂) as single scheduling units.

A requirement with a lesson_pattern such as "2+1" has its lessons grouped
into blocks (resources.lesson_blocks). The search treats every block as ONE
unit: its candidates are (teacher, start window, room), where a window is
a run of `size` consecutive teaching periods on one day; placing a unit
expands it into one LessonAssignment per lesson -- the first lesson in the
first period of the window, and so on -- all with the same teacher and
room. Every existing constraint then checks those assignments exactly as
it checks single lessons. Different blocks of one requirement must be on
different days (constraints/lesson_block.py, real-time).

A lesson in no block is a unit of its own whose candidates are exactly the
(teacher, time slot, room) combinations the algorithms always generated,
in the same order -- so without blocks, nothing about the search changes.

共同排課: a 合併節 (resources.combined_lessons) is one unit too -- every
member's lessons of it, placed in the same slot (or the same window, for
blocks) with the combined lesson's room. Its teachers are fixed when the
members name any (each member keeps its own required teacher, the others
get the first named one); otherwise one teacher is searched for all of them.

"Consecutive" = same weekday, period numbers p, p+1, ..., every one of
them a teaching period (a non-teaching period such as lunch in between
breaks the run, and so does a missing period).
"""

from collections.abc import Iterator
from dataclasses import dataclass, replace

from scheduling_engine.algorithms.resources import (
    LookupTables,
    SchedulingResources,
    allowed_time_slots_of_class,
    candidate_room_ids,
    candidate_teacher_ids,
    candidate_time_slot_ids,
)
from scheduling_engine.constraints.base import BaseConstraint, ConstraintViolation, Severity
from scheduling_engine.constraints.lesson_block import LessonBlockConstraint
from scheduling_engine.models.domain import CombinedLesson, LessonAssignment, LessonBlock


@dataclass(frozen=True)
class SchedulingUnit:
    """One thing the search places at once: a single lesson (block None),
    or every lesson of one block, in block order -- or (combined set) every
    member's lessons of one 合併節, member by member."""

    lessons: tuple[LessonAssignment, ...]
    block: LessonBlock | None
    combined: CombinedLesson | None = None

    @property
    def span(self) -> int:
        """How many consecutive periods the unit takes."""
        if self.combined is not None:
            return len(self.combined.member_lesson_ids[0])
        return len(self.lessons)


def teaching_runs(resources: SchedulingResources) -> list[list[int]]:
    """Maximal runs of consecutive teaching periods, one list of time slot
    ids per run, ordered by weekday then period. A slot without a
    TimeSlotInfo counts as teaching (same "unknown is not a violation"
    stance as H11)."""
    teaching = {slot.time_slot_id: slot.is_teaching_period for slot in resources.time_slots}
    by_day: dict[int, list[tuple[int, int]]] = {}
    for position in resources.time_slot_positions:
        if teaching.get(position.time_slot_id, True):
            by_day.setdefault(position.weekday, []).append((position.period, position.time_slot_id))
    runs: list[list[int]] = []
    for weekday in sorted(by_day):
        current: list[int] = []
        previous_period: int | None = None
        for period, slot_id in sorted(by_day[weekday]):
            if previous_period is not None and period == previous_period + 1:
                current.append(slot_id)
            else:
                if current:
                    runs.append(current)
                current = [slot_id]
            previous_period = period
        if current:
            runs.append(current)
    return runs


def weekday_by_slot(resources: SchedulingResources) -> dict[int, int]:
    return {position.time_slot_id: position.weekday for position in resources.time_slot_positions}


def block_windows(size: int, resources: SchedulingResources) -> list[tuple[int, ...]]:
    """Every run of `size` consecutive teaching periods on one day, as the
    time slot ids in period order. Ordered by where the window's first slot
    appears in resources.time_slot_ids -- the order single lessons try time
    slots in -- so the search stays deterministic."""
    order = {slot_id: index for index, slot_id in enumerate(resources.time_slot_ids)}
    windows = [
        tuple(run[start : start + size])
        for run in teaching_runs(resources)
        for start in range(len(run) - size + 1)
    ]
    return sorted(windows, key=lambda window: order.get(window[0], len(order)))


def build_units(
    lessons: list[LessonAssignment], resources: SchedulingResources
) -> list[SchedulingUnit]:
    """The lessons as scheduling units, in the order of `lessons` (a block
    or a 合併節 takes the place of its first lesson in that list). Without
    blocks or combined lessons this is exactly one unit per lesson, in the
    same order."""
    if not resources.lesson_blocks and not resources.combined_lessons:
        return [SchedulingUnit((lesson,), None) for lesson in lessons]
    combined_of: dict[int, CombinedLesson] = {
        lesson_id: combined
        for combined in resources.combined_lessons
        for lesson_ids in combined.member_lesson_ids
        for lesson_id in lesson_ids
    }
    block_of: dict[int, LessonBlock] = {}
    for block in resources.lesson_blocks:
        for lesson_id in block.lesson_ids:
            block_of[lesson_id] = block
    by_id = {lesson.lesson_id: lesson for lesson in lessons}
    units: list[SchedulingUnit] = []
    seen_blocks: set[tuple[int, int]] = set()
    seen_combined: set[str] = set()
    for lesson in lessons:
        combined = combined_of.get(lesson.lesson_id)
        if combined is not None:
            if combined.key in seen_combined:
                continue
            seen_combined.add(combined.key)
            members = tuple(
                by_id[lesson_id]
                for lesson_ids in combined.member_lesson_ids
                for lesson_id in lesson_ids
                if lesson_id in by_id
            )
            units.append(SchedulingUnit(members, None, combined))
            continue
        block = block_of.get(lesson.lesson_id)
        if block is None:
            units.append(SchedulingUnit((lesson,), None))
            continue
        key = (block.class_subject_requirement_id, block.block_no)
        if key in seen_blocks:
            continue
        seen_blocks.add(key)
        members = tuple(by_id[lesson_id] for lesson_id in block.lesson_ids if lesson_id in by_id)
        units.append(SchedulingUnit(members, block))
    return units


def unit_windows(unit: SchedulingUnit, resources: SchedulingResources) -> list[tuple[int, ...]]:
    """A block's (or a 合併節's) start windows, keeping only those that put
    every fixed lesson (pending time_slot_id already set, Task 28) in its
    fixed slot -- for a 合併節, a fixed lesson of any member fixes all of
    it. Task 98 (H13): and only windows entirely inside the time slots
    every class's grade is open for."""
    windows = block_windows(unit.span, resources)
    for class_id in sorted({lesson.class_id for lesson in unit.lessons}):
        allowed = allowed_time_slots_of_class(class_id, resources)
        if allowed is not None:
            windows = [window for window in windows if all(slot_id in allowed for slot_id in window)]
    for lesson in unit.lessons:
        if lesson.time_slot_id is not None:
            index = _position_in_unit(unit, lesson.lesson_id)
            windows = [window for window in windows if window[index] == lesson.time_slot_id]
    return windows


def _position_in_unit(unit: SchedulingUnit, lesson_id: int) -> int:
    """Which period of the unit's window the lesson takes."""
    if unit.combined is not None:
        for lesson_ids in unit.combined.member_lesson_ids:
            if lesson_id in lesson_ids:
                return lesson_ids.index(lesson_id)
    return [lesson.lesson_id for lesson in unit.lessons].index(lesson_id)


def _combined_teacher_choices(
    unit: SchedulingUnit, tables: LookupTables
) -> list[dict[int, int]]:
    """lesson_id -> teacher, one dict per way of staffing a 合併節: the
    members' named teachers (see the module docstring), or each teacher
    taking part alone."""
    assert unit.combined is not None
    named = unit.combined.teacher_ids
    if named:
        default = named[0]
        return [
            {
                lesson.lesson_id: tables.required_teacher_by_requirement.get(
                    lesson.class_subject_requirement_id, default
                )
                for lesson in unit.lessons
            }
        ]
    return [{lesson.lesson_id: teacher_id for lesson in unit.lessons} for teacher_id in tables.teacher_ids]


def unit_candidate_count(
    unit: SchedulingUnit, resources: SchedulingResources, tables: LookupTables
) -> int:
    """MRV key. For a single lesson it is the same product the algorithms
    always sorted by (teachers x time slots x rooms)."""
    first = unit.lessons[0]
    if unit.combined is not None:
        return len(_combined_teacher_choices(unit, tables)) * len(unit_windows(unit, resources))
    slots = (
        len(candidate_time_slot_ids(first, resources))
        if unit.block is None
        else len(unit_windows(unit, resources))
    )
    return len(candidate_teacher_ids(first, tables)) * slots * len(candidate_room_ids(first, tables))


def iter_unit_candidates(
    unit: SchedulingUnit, resources: SchedulingResources, tables: LookupTables
) -> Iterator[tuple[LessonAssignment, ...]]:
    """Every placement of the unit, one LessonAssignment per lesson. A
    single lesson: teacher x time slot x room, in the algorithms' original
    order. A block: teacher x start window x room, the whole block with one
    teacher and one room."""
    first = unit.lessons[0]
    if unit.combined is not None:
        room_id = unit.combined.room_id
        for teachers_of in _combined_teacher_choices(unit, tables):
            for window in unit_windows(unit, resources):
                yield tuple(
                    replace(
                        lesson,
                        teacher_id=teachers_of[lesson.lesson_id],
                        time_slot_id=window[_position_in_unit(unit, lesson.lesson_id)],
                        room_id=room_id,
                    )
                    for lesson in unit.lessons
                )
        return
    teachers = candidate_teacher_ids(first, tables)
    rooms = candidate_room_ids(first, tables)
    if unit.block is None:
        for teacher_id in teachers:
            for time_slot_id in candidate_time_slot_ids(first, resources):
                for room_id in rooms:
                    yield (
                        replace(first, teacher_id=teacher_id, time_slot_id=time_slot_id, room_id=room_id),
                    )
        return
    windows = unit_windows(unit, resources)
    for teacher_id in teachers:
        for window in windows:
            for room_id in rooms:
                yield tuple(
                    replace(lesson, teacher_id=teacher_id, time_slot_id=slot_id, room_id=room_id)
                    for lesson, slot_id in zip(unit.lessons, window)
                )


def block_constraints(resources: SchedulingResources) -> list[BaseConstraint]:
    """The real-time block rule, only when there are blocks -- without them
    the algorithms run exactly the constraint list they always did."""
    if not resources.lesson_blocks:
        return []
    return [
        LessonBlockConstraint(
            resources.lesson_blocks, resources.time_slot_positions, resources.time_slots
        )
    ]


def no_block_window_violation(unit: SchedulingUnit) -> ConstraintViolation:
    """A block with no window of consecutive teaching periods at all (or
    none that keeps its fixed lessons in their fixed slots)."""
    first = unit.lessons[0]
    block_no = unit.block.block_no if unit.block is not None else None
    return ConstraintViolation(
        type="BLOCK_NO_WINDOW",
        severity=Severity.ERROR,
        lesson_id=first.lesson_id,
        teacher_id=None,
        class_id=first.class_id,
        subject_id=first.subject_id,
        time_slot_id=None,
        class_subject_requirement_id=first.class_subject_requirement_id,
        message=(
            f"Block {block_no} ({len(unit.lessons)} lessons) of requirement "
            f"{first.class_subject_requirement_id} has no {len(unit.lessons)} consecutive "
            "teaching periods on one day that it could use."
        ),
        suggested_action="Change the lesson pattern, its fixed time slots, or the time slots.",
    )
