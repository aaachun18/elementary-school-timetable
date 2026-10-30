"""Soft constraints, scored together after the search:

- S8 國語文、數學 in the first two teaching periods of the day (第 1–2 節):
  +1 for every such lesson there;
- S9 體育 not in 第 1、4、5 節 (each day's 1st, 4th and 5th teaching
  period -- 第 5 節 is the first one after 午休): -1 for every such lesson
  there;
- S10 (國小) the last period of a class's full days (a day it has lessons
  both before and after a non-teaching break such as 午休) holds an
  activity subject (活動性課程 -- the service decides which subjects those
  are): +1 for every such lesson there.

Runs only AFTER the search has produced a complete, legal timetable, and
only ever replaces it by another complete, legal one: every hard constraint
is satisfied first, then -- school-wide -- the total score is raised as far
as the method below gets it; higher is better. Every preference weighs the
same (one lesson, one point).

Method: hill climbing with two kinds of step, applied to one scheduling unit
(a single lesson, or a whole lesson block -- algorithms/blocks.py) that
could score more somewhere else:

- move: the unit goes to a target (one slot, or a window of consecutive
  slots for a block) that its class has free;
- swap: the class's lessons occupying that target trade places with the
  unit -- a single lesson for a single lesson, or one block for a block of
  the same size, or as many single lessons as the block is long.

Every unit keeps its teacher and room; only time slots change. A step is
taken only when it raises the total score of the lessons it moves, keeps
every real-time hard constraint (the same ones the search checks: H1-H6,
H8, H9, H11-H15 and the block rules) satisfied for the whole timetable, and
doesn't put more of a requirement's separate (non-block) lessons on one day
than it already had -- so the spread across the week never gets worse.
Fixed lessons (a fixed time slot) and the lessons of a combined lesson
(共同排課, several classes at once) never move. Steps are tried in a fixed
order, so the same input always gives the same result; max_checks /
timeout_seconds bound the work.

Pure: no database, no FastAPI (AGENTS.md section 4).
"""

import time
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, replace

from scheduling_engine.algorithms.blocks import (
    block_constraints,
    block_windows,
    build_units,
    teaching_runs,
)
from scheduling_engine.algorithms.resources import (
    SchedulingResources,
    allowed_time_slots_of_class,
    build_real_time_constraints,
)
from scheduling_engine.models.domain import LessonAssignment, joint_keys

# 第 1–2 節: how many of each day's first teaching periods are preferred.
PREFERRED_PERIODS_PER_DAY = 2
# S9: the teaching periods (1 = 第 1 節) 體育 should stay out of.
AVOIDED_TEACHING_PERIODS = (1, 4, 5)
DEFAULT_MAX_CHECKS = 20000
DEFAULT_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class SoftPreferences:
    """Which subjects each soft constraint is about (see the module
    docstring). An empty set switches that preference off."""

    preferred_subject_ids: frozenset[int] = frozenset()
    avoided_subject_ids: frozenset[int] = frozenset()
    activity_subject_ids: frozenset[int] = frozenset()

    def all_subject_ids(self) -> frozenset[int]:
        return self.preferred_subject_ids | self.avoided_subject_ids | self.activity_subject_ids


@dataclass
class PreferredPeriodsResult:
    """The improved timetable (same lessons, teachers and rooms; only time
    slots may differ) and how it scores: the total soft score before and
    after, plus each preference on its own (after):
    - preferred_in_place / preferred_lesson_count: 國語文、數學 in 第 1–2 節;
    - avoided_in_place: 體育 lessons still in 第 1、4、5 節;
    - activity_in_last_periods / last_period_count: full days' last periods
      holding an activity subject, out of how many such periods there are."""

    assignments: list[LessonAssignment]
    score_before: int
    score_after: int
    preferred_lesson_count: int
    steps_taken: int
    checks_used: int
    preferred_in_place: int = 0
    avoided_in_place: int = 0
    activity_in_last_periods: int = 0
    last_period_count: int = 0


def _teaching_slots_by_day(resources: SchedulingResources) -> dict[int, list[int]]:
    """weekday -> its teaching time slots in period order. A slot without a
    TimeSlotInfo counts as teaching, as elsewhere."""
    teaching = {slot.time_slot_id: slot.is_teaching_period for slot in resources.time_slots}
    by_day: dict[int, list[tuple[int, int]]] = {}
    for position in resources.time_slot_positions:
        if teaching.get(position.time_slot_id, True):
            by_day.setdefault(position.weekday, []).append((position.period, position.time_slot_id))
    return {day: [slot_id for _, slot_id in sorted(slots)] for day, slots in by_day.items()}


def preferred_time_slot_ids(
    resources: SchedulingResources, per_day: int = PREFERRED_PERIODS_PER_DAY
) -> frozenset[int]:
    """Each weekday's first `per_day` teaching periods (第 1–2 節), whatever
    their raw period numbers (period 0 is usually 早自習, not teaching)."""
    return frozenset(
        slot_id
        for day_slots in _teaching_slots_by_day(resources).values()
        for slot_id in day_slots[:per_day]
    )


def avoided_time_slot_ids(
    resources: SchedulingResources, teaching_periods: tuple[int, ...] = AVOIDED_TEACHING_PERIODS
) -> frozenset[int]:
    """S9: each weekday's n-th teaching periods for n in `teaching_periods`
    (第 1、4、5 節), counted like 第 1–2 節 above."""
    return frozenset(
        day_slots[number - 1]
        for day_slots in _teaching_slots_by_day(resources).values()
        for number in teaching_periods
        if number <= len(day_slots)
    )


def last_time_slot_ids_by_class(
    class_ids: set[int], resources: SchedulingResources
) -> dict[int, frozenset[int]]:
    """S10: class -> the last teaching period of each of its full days. A
    full day is one whose teaching periods open to the class (H13) lie in
    more than one run of consecutive teaching periods -- lessons before and
    after 午休; its last period is the latest of them."""
    run_of = {
        slot_id: index for index, run in enumerate(teaching_runs(resources)) for slot_id in run
    }
    by_day = _teaching_slots_by_day(resources)
    result: dict[int, frozenset[int]] = {}
    for class_id in sorted(class_ids):
        allowed = allowed_time_slots_of_class(class_id, resources)
        last_slots: set[int] = set()
        for day_slots in by_day.values():
            open_slots = [slot_id for slot_id in day_slots if allowed is None or slot_id in allowed]
            if len({run_of.get(slot_id) for slot_id in open_slots}) > 1:
                last_slots.add(open_slots[-1])
        result[class_id] = frozenset(last_slots)
    return result


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


@dataclass(frozen=True)
class _Scorer:
    """One lesson's soft score in a time slot (see the module docstring)."""

    preferences: SoftPreferences
    preferred_slot_ids: frozenset[int]
    avoided_slot_ids: frozenset[int]
    last_slots_by_class: dict[int, frozenset[int]]

    def lesson_score(self, assignment: LessonAssignment, slot_id: int | None) -> int:
        subject_id = assignment.subject_id
        score = 0
        if subject_id in self.preferences.preferred_subject_ids and slot_id in self.preferred_slot_ids:
            score += 1
        if subject_id in self.preferences.avoided_subject_ids and slot_id in self.avoided_slot_ids:
            score -= 1
        if subject_id in self.preferences.activity_subject_ids and slot_id in self.last_slots_by_class.get(
            assignment.class_id, frozenset()
        ):
            score += 1
        return score

    def total(self, assignments: list[LessonAssignment]) -> int:
        return sum(self.lesson_score(assignment, assignment.time_slot_id) for assignment in assignments)


class _Optimizer:
    def __init__(
        self,
        assignments: list[LessonAssignment],
        pending_lessons: list[LessonAssignment],
        resources: SchedulingResources,
        scorer: _Scorer,
        max_checks: int,
        timeout_seconds: float,
    ) -> None:
        self.resources = resources
        self.scorer = scorer
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
        # (class, slot) -> the lessons there, kept in step with `placed`.
        self.at: dict[tuple[int, int | None], set[int]] = defaultdict(set)
        for assignment in assignments:
            self.at[(assignment.class_id, assignment.time_slot_id)].add(assignment.lesson_id)
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
        self.windows_by_size: dict[int, list[tuple[int, ...]]] = {
            1: [(slot_id,) for slot_id in resources.time_slot_ids]
        }
        # The spread guard's ceiling: each requirement's most separate
        # lessons on one day in the starting timetable.
        self.day_limit = self._separate_lessons_per_day(self.placed)

    # --- bookkeeping ---

    def out_of_budget(self) -> bool:
        return self.checks_used >= self.max_checks or time.monotonic() > self.deadline

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

    def slots_of(self, unit: tuple[int, ...]) -> tuple[int, ...]:
        return tuple(self.placed[lesson_id].time_slot_id for lesson_id in unit)  # type: ignore[misc]

    def unit_score(self, unit: tuple[int, ...], window: tuple[int, ...]) -> int:
        return sum(
            self.scorer.lesson_score(self.placed[lesson_id], slot_id)
            for lesson_id, slot_id in zip(unit, window, strict=True)
        )

    def is_movable(self, unit: tuple[int, ...]) -> bool:
        return not any(lesson_id in self.fixed_lesson_ids for lesson_id in unit)

    def is_concerned(self, unit: tuple[int, ...]) -> bool:
        """The unit's subject is one any soft constraint is about."""
        return self.placed[unit[0]].subject_id in self.scorer.preferences.all_subject_ids()

    def windows(self, size: int) -> list[tuple[int, ...]]:
        if size not in self.windows_by_size:
            self.windows_by_size[size] = block_windows(size, self.resources)
        return self.windows_by_size[size]

    # --- candidate steps ---

    def targets(self, unit: tuple[int, ...]) -> list[tuple[int, ...]]:
        """Where the unit itself would score more: single slots, or windows
        of consecutive teaching periods (a block) -- best first, then in
        slot order."""
        current = self.unit_score(unit, self.slots_of(unit))
        scored = [(self.unit_score(unit, window), window) for window in self.windows(len(unit))]
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
        occupying = sorted(
            lesson_id
            for slot_id in target
            for lesson_id in self.at.get((class_id, slot_id), ())
            if lesson_id not in unit
        )
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
        """Applies the step if it raises the score of the lessons it moves
        and keeps the timetable legal (and the spread no worse); returns
        whether it did."""
        before = sum(
            self.scorer.lesson_score(self.placed[lesson_id], self.placed[lesson_id].time_slot_id)
            for lesson_id in changes
        )
        after = sum(
            self.scorer.lesson_score(self.placed[lesson_id], slot_id)
            for lesson_id, slot_id in changes.items()
        )
        if after <= before:
            return False
        candidate = dict(self.placed)
        for lesson_id, slot_id in changes.items():
            candidate[lesson_id] = replace(candidate[lesson_id], time_slot_id=slot_id)
        spread = self._separate_lessons_per_day(candidate)
        if any(count > self.day_limit.get(requirement_id, 0) for requirement_id, count in spread.items()):
            return False
        self.checks_used += 1
        ordered = [candidate[lesson_id] for lesson_id in self.order]
        if not all(constraint.validate(ordered) for constraint in self.constraints):
            return False
        for lesson_id in changes:
            old = self.placed[lesson_id]
            self.at[(old.class_id, old.time_slot_id)].discard(lesson_id)
            self.at[(old.class_id, candidate[lesson_id].time_slot_id)].add(lesson_id)
        self.placed = candidate
        return True

    def improvable_units(self) -> Iterator[tuple[tuple[int, ...], list[tuple[int, ...]]]]:
        """Every movable unit of a concerned subject, with where it would
        score more."""
        for unit in self.units:
            if not self.is_movable(unit) or not self.is_concerned(unit):
                continue
            targets = self.targets(unit)
            if targets:
                yield unit, targets

    def run(self) -> int:
        steps = 0
        improved = True
        while improved and not self.out_of_budget():
            improved = False
            for unit, targets in self.improvable_units():
                if self.out_of_budget():
                    break
                for target in targets:
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
    avoided_subject_ids: frozenset[int] = frozenset(),
    activity_subject_ids: frozenset[int] = frozenset(),
    max_checks: int = DEFAULT_MAX_CHECKS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> PreferredPeriodsResult:
    """`assignments`: a complete, legal timetable of `pending_lessons` (the
    lessons as handed to the search; a set time_slot_id there = fixed).
    Returns it improved for the soft constraints (see the module
    docstring), in the same order; unchanged when there is nothing to
    prefer. preferred_subject_ids: S8 (國語文、數學); avoided_subject_ids:
    S9 (體育); activity_subject_ids: S10 (活動性課程)."""
    preferences = SoftPreferences(preferred_subject_ids, avoided_subject_ids, activity_subject_ids)
    preferred_slots = preferred_time_slot_ids(resources)
    last_slots = last_time_slot_ids_by_class(
        {assignment.class_id for assignment in assignments}, resources
    )
    scorer = _Scorer(preferences, preferred_slots, avoided_time_slot_ids(resources), last_slots)

    def result_for(improved: list[LessonAssignment], steps: int, checks: int) -> PreferredPeriodsResult:
        return PreferredPeriodsResult(
            assignments=improved,
            score_before=scorer.total(assignments),
            score_after=scorer.total(improved),
            preferred_lesson_count=sum(
                1 for assignment in improved if assignment.subject_id in preferred_subject_ids
            ),
            steps_taken=steps,
            checks_used=checks,
            preferred_in_place=preferred_period_score(improved, preferred_subject_ids, preferred_slots),
            avoided_in_place=sum(
                1
                for assignment in improved
                if assignment.subject_id in avoided_subject_ids
                and assignment.time_slot_id in scorer.avoided_slot_ids
            ),
            activity_in_last_periods=sum(
                1
                for assignment in improved
                if assignment.subject_id in activity_subject_ids
                and assignment.time_slot_id in last_slots.get(assignment.class_id, frozenset())
            ),
            last_period_count=(
                sum(len(slots) for slots in last_slots.values()) if activity_subject_ids else 0
            ),
        )

    subject_ids = {assignment.subject_id for assignment in assignments}
    if not preferences.all_subject_ids() & subject_ids:
        return result_for(list(assignments), 0, 0)
    optimizer = _Optimizer(assignments, pending_lessons, resources, scorer, max_checks, timeout_seconds)
    steps = optimizer.run()
    improved = [optimizer.placed[assignment.lesson_id] for assignment in assignments]
    return result_for(improved, steps, optimizer.checks_used)
