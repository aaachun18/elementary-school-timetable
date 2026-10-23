"""Soft constraint: preferred subjects (國語文、數學) in the first two
teaching periods of the day (第 1–2 節).

Runs only AFTER the search has produced a complete, legal timetable, and
only ever replaces it by another complete, legal one: every hard constraint
is satisfied first, then -- school-wide -- as many preferred-subject lessons
as possible are brought into the preferred periods. The score is simply that
count; higher is better.

Method: hill climbing with two kinds of step, applied to one scheduling unit
(a single lesson, or a whole lesson block -- algorithms/blocks.py) of a
preferred subject that is not yet (fully) in the preferred periods:

- move: the unit goes to a target in the preferred periods (one slot, or a
  window of consecutive slots for a block) that its class has free;
- swap: the class's lessons occupying that target trade places with the
  unit -- a single lesson for a single lesson, or one block for a block of
  the same size, or as many single lessons as the block is long.

Every unit keeps its teacher and room; only time slots change. A step is
taken only when it raises the score, keeps every real-time hard constraint
(the same ones the search checks: H1-H6, H8, H9, H11-H13 and the block
rules) satisfied for the whole timetable, and doesn't put more of a
requirement's separate (non-block) lessons on one day than it already had
-- so the spread across the week never gets worse. Fixed lessons (a fixed
time slot) and the lessons of a combined lesson (共同排課, several classes
at once) never move. Steps are tried in a fixed order, so the same input
always gives the same result; max_checks / timeout_seconds bound the work.

Pure: no database, no FastAPI (AGENTS.md section 4).
"""

import time
from collections.abc import Iterator
from dataclasses import dataclass, replace

from scheduling_engine.algorithms.blocks import (
    SchedulingUnit,
    block_constraints,
    block_windows,
    build_units,
)
from scheduling_engine.algorithms.resources import (
    SchedulingResources,
    build_real_time_constraints,
)
from scheduling_engine.models.domain import LessonAssignment, joint_keys

# 第 1–2 節: how many of each day's first teaching periods are preferred.
PREFERRED_PERIODS_PER_DAY = 2
DEFAULT_MAX_CHECKS = 20000
DEFAULT_TIMEOUT_SECONDS = 15.0


@dataclass
class PreferredPeriodsResult:
    """The improved timetable (same lessons, teachers and rooms; only time
    slots may differ) and how it scores: preferred-subject lessons in the
    preferred periods, before and after, out of preferred_lesson_count."""

    assignments: list[LessonAssignment]
    score_before: int
    score_after: int
    preferred_lesson_count: int
    steps_taken: int
    checks_used: int


def preferred_time_slot_ids(
    resources: SchedulingResources, per_day: int = PREFERRED_PERIODS_PER_DAY
) -> frozenset[int]:
    """Each weekday's first `per_day` teaching periods (第 1–2 節), whatever
    their raw period numbers (period 0 is usually 早自習, not teaching). A
    slot without a TimeSlotInfo counts as teaching, as elsewhere."""
    teaching = {slot.time_slot_id: slot.is_teaching_period for slot in resources.time_slots}
    by_day: dict[int, list[tuple[int, int]]] = {}
    for position in resources.time_slot_positions:
        if teaching.get(position.time_slot_id, True):
            by_day.setdefault(position.weekday, []).append((position.period, position.time_slot_id))
    return frozenset(
        slot_id
        for day_slots in by_day.values()
        for _, slot_id in sorted(day_slots)[:per_day]
    )


def preferred_period_score(
    assignments: list[LessonAssignment],
    preferred_subject_ids: frozenset[int],
    preferred_slot_ids: frozenset[int],
) -> int:
    return sum(
        1
        for assignment in assignments
        if assignment.subject_id in preferred_subject_ids
        and assignment.time_slot_id in preferred_slot_ids
    )


class _Optimizer:
    def __init__(
        self,
        assignments: list[LessonAssignment],
        pending_lessons: list[LessonAssignment],
        resources: SchedulingResources,
        preferred_subject_ids: frozenset[int],
        preferred_slot_ids: frozenset[int],
        max_checks: int,
        timeout_seconds: float,
    ) -> None:
        self.resources = resources
        self.preferred_subject_ids = preferred_subject_ids
        self.preferred_slot_ids = preferred_slot_ids
        self.max_checks = max_checks
        self.deadline = time.monotonic() + timeout_seconds
        self.checks_used = 0
        self.constraints = [
            *build_real_time_constraints(resources, include_teacher_workload=True),
            *block_constraints(resources),
        ]
        self.fixed_lesson_ids = {
            lesson.lesson_id for lesson in pending_lessons if lesson.time_slot_id is not None
        } | set(joint_keys(resources.combined_lessons))
        # lesson_id -> its current assignment (the timetable being improved).
        self.placed = {assignment.lesson_id: assignment for assignment in assignments}
        self.order = [assignment.lesson_id for assignment in assignments]
        self.units = [
            tuple(lesson.lesson_id for lesson in unit.lessons)
            for unit in build_units(
                sorted(pending_lessons, key=lambda lesson: lesson.lesson_id), resources
            )
            if all(lesson.lesson_id in self.placed for lesson in unit.lessons)
        ]
        self.unit_of = {lesson_id: unit for unit in self.units for lesson_id in unit}
        self.blocked_lesson_ids = {
            lesson_id for block in resources.lesson_blocks for lesson_id in block.lesson_ids
        }
        self.weekday_of = {
            position.time_slot_id: position.weekday for position in resources.time_slot_positions
        }
        self.slot_rank = {slot_id: index for index, slot_id in enumerate(resources.time_slot_ids)}
        # The spread guard's ceiling: each requirement's most separate
        # lessons on one day in the starting timetable.
        self.day_limit = self._separate_lessons_per_day_max()

    # --- bookkeeping ---

    def out_of_budget(self) -> bool:
        return self.checks_used >= self.max_checks or time.monotonic() > self.deadline

    def score(self) -> int:
        return preferred_period_score(
            list(self.placed.values()), self.preferred_subject_ids, self.preferred_slot_ids
        )

    def _separate_lessons_per_day(self, placed: dict[int, LessonAssignment]) -> dict[int, int]:
        """requirement -> its most non-block lessons on any one day."""
        counts: dict[tuple[int, int], int] = {}
        for assignment in placed.values():
            if assignment.lesson_id in self.blocked_lesson_ids or assignment.time_slot_id is None:
                continue
            key = (
                assignment.class_subject_requirement_id,
                self.weekday_of.get(assignment.time_slot_id, -1),
            )
            counts[key] = counts.get(key, 0) + 1
        most: dict[int, int] = {}
        for (requirement_id, _), count in counts.items():
            most[requirement_id] = max(most.get(requirement_id, 0), count)
        return most

    def _separate_lessons_per_day_max(self) -> dict[int, int]:
        return self._separate_lessons_per_day(self.placed)

    def slots_of(self, unit: tuple[int, ...]) -> tuple[int, ...]:
        return tuple(self.placed[lesson_id].time_slot_id for lesson_id in unit)  # type: ignore[misc]

    def is_preferred_unit(self, unit: tuple[int, ...]) -> bool:
        return self.placed[unit[0]].subject_id in self.preferred_subject_ids

    def is_movable(self, unit: tuple[int, ...]) -> bool:
        return not any(lesson_id in self.fixed_lesson_ids for lesson_id in unit)

    # --- candidate steps ---

    def targets(self, unit: tuple[int, ...]) -> list[tuple[int, ...]]:
        """Where the unit could go that puts more of it in the preferred
        periods: preferred single slots, or windows of consecutive teaching
        periods (a block) touching them -- best first, then in slot order."""
        current = sum(1 for slot_id in self.slots_of(unit) if slot_id in self.preferred_slot_ids)
        if len(unit) == 1:
            windows = [(slot_id,) for slot_id in self.resources.time_slot_ids]
        else:
            windows = block_windows(len(unit), self.resources)
        scored = [
            (sum(1 for slot_id in window if slot_id in self.preferred_slot_ids), window)
            for window in windows
        ]
        better = [(gain, window) for gain, window in scored if gain > current]
        better.sort(key=lambda item: (-item[0], self.slot_rank.get(item[1][0], 0)))
        return [window for _, window in better]

    def step_for(
        self, unit: tuple[int, ...], target: tuple[int, ...]
    ) -> dict[int, int] | None:
        """lesson_id -> new time slot for moving `unit` to `target`, plus
        whatever of its class has to trade places with it there -- or None
        when no such simple step exists."""
        class_id = self.placed[unit[0]].class_id
        own_slots = self.slots_of(unit)
        occupying = [
            lesson_id
            for lesson_id, assignment in self.placed.items()
            if assignment.class_id == class_id
            and assignment.time_slot_id in target
            and lesson_id not in unit
        ]
        changes = dict(zip(unit, target, strict=True))
        if not occupying:
            return changes
        others = sorted({self.unit_of[lesson_id] for lesson_id in occupying if lesson_id in self.unit_of})
        if len(occupying) != sum(len(other) for other in others):
            return None  # a lesson the optimizer doesn't know as a unit
        if any(not self.is_movable(other) for other in others):
            return None
        # Everything the others hold must lie inside the target, and they
        # move into the unit's old slots.
        if any(slot_id not in target for other in others for slot_id in self.slots_of(other)):
            return None
        if sum(len(other) for other in others) != len(own_slots):
            return None
        if len(others) == 1:
            changes.update(zip(others[0], own_slots, strict=True))
            return changes
        if all(len(other) == 1 for other in others):
            # Single lessons fill the old slots in order.
            for other, slot_id in zip(others, own_slots, strict=True):
                changes[other[0]] = slot_id
            return changes
        return None

    def try_step(self, changes: dict[int, int]) -> bool:
        """Applies the step if it raises the score and keeps the timetable
        legal (and the spread no worse); returns whether it did."""
        candidate = dict(self.placed)
        for lesson_id, slot_id in changes.items():
            candidate[lesson_id] = replace(candidate[lesson_id], time_slot_id=slot_id)
        before = preferred_period_score(
            [self.placed[lesson_id] for lesson_id in changes],
            self.preferred_subject_ids,
            self.preferred_slot_ids,
        )
        after = preferred_period_score(
            [candidate[lesson_id] for lesson_id in changes],
            self.preferred_subject_ids,
            self.preferred_slot_ids,
        )
        if after <= before:
            return False
        spread = self._separate_lessons_per_day(candidate)
        if any(count > self.day_limit.get(requirement_id, 0) for requirement_id, count in spread.items()):
            return False
        self.checks_used += 1
        ordered = [candidate[lesson_id] for lesson_id in self.order]
        if not all(constraint.validate(ordered) for constraint in self.constraints):
            return False
        self.placed = candidate
        return True

    def improvable_units(self) -> Iterator[tuple[int, ...]]:
        for unit in self.units:
            if not self.is_preferred_unit(unit) or not self.is_movable(unit):
                continue
            if all(slot_id in self.preferred_slot_ids for slot_id in self.slots_of(unit)):
                continue
            yield unit

    def run(self) -> int:
        steps = 0
        improved = True
        while improved and not self.out_of_budget():
            improved = False
            for unit in self.improvable_units():
                if self.out_of_budget():
                    break
                for target in self.targets(unit):
                    changes = self.step_for(unit, target)
                    if changes is not None and self.try_step(changes):
                        steps += 1
                        improved = True
                        break
                    if self.out_of_budget():
                        break
        return steps


def optimize_preferred_periods(
    assignments: list[LessonAssignment],
    pending_lessons: list[LessonAssignment],
    resources: SchedulingResources,
    preferred_subject_ids: frozenset[int],
    *,
    max_checks: int = DEFAULT_MAX_CHECKS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> PreferredPeriodsResult:
    """`assignments`: a complete, legal timetable of `pending_lessons` (the
    lessons as handed to the search; a set time_slot_id there = fixed).
    Returns it improved for the soft constraint (see the module docstring),
    in the same order; unchanged when there is nothing to prefer."""
    preferred_slots = preferred_time_slot_ids(resources)
    preferred_count = sum(
        1 for assignment in assignments if assignment.subject_id in preferred_subject_ids
    )
    score_before = preferred_period_score(assignments, preferred_subject_ids, preferred_slots)
    if not preferred_subject_ids or not preferred_slots or preferred_count == 0:
        return PreferredPeriodsResult(
            assignments=list(assignments),
            score_before=score_before,
            score_after=score_before,
            preferred_lesson_count=preferred_count,
            steps_taken=0,
            checks_used=0,
        )
    optimizer = _Optimizer(
        assignments,
        pending_lessons,
        resources,
        preferred_subject_ids,
        preferred_slots,
        max_checks,
        timeout_seconds,
    )
    steps = optimizer.run()
    improved = [optimizer.placed[assignment.lesson_id] for assignment in assignments]
    return PreferredPeriodsResult(
        assignments=improved,
        score_before=score_before,
        score_after=optimizer.score(),
        preferred_lesson_count=preferred_count,
        steps_taken=steps,
        checks_used=optimizer.checks_used,
    )
