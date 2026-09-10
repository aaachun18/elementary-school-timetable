"""Backtracking Scheduler.

Same MRV ordering and candidate generation as Greedy (schedule_greedy),
reused via algorithms/resources.py rather than duplicated -- see that
module's docstring. The difference is entirely in what happens when a
Lesson has no valid candidate: instead of giving up immediately, this
retracts the PREVIOUS Lesson's commitment and resumes trying that
Lesson's remaining candidates from where it left off (not from scratch,
and not by re-sorting the whole list -- the MRV order itself never
changes mid-search).

Why H8 is real-time here but H7 still isn't
--------------------------------------------
This continues the discussion started in greedy.py's module docstring
(then in the Task 19 report). H8 ("<=" a ceiling) and H7 ("==" an exact
target) are different in kind:

- H8 is safe to check per-candidate: "would adding this candidate push the
  teacher over their max?" has a definite answer given only the current
  state, and once satisfied it stays satisfied as the search adds more
  assignments elsewhere. Task 19 chose not to bother with this for Greedy,
  since Greedy can't act on an early rejection anyway (it never
  reconsiders a prior choice) -- real-time H8 filtering would only change
  which Lesson the inevitable failure shows up at, not whether the run
  succeeds. Backtracking is different: it CAN act on an early rejection,
  by trying a different candidate for an earlier Lesson. So here,
  filtering out over-cap candidates before they're ever committed lets the
  search avoid wandering into (and having to backtrack out of) a doomed
  branch, which is strictly better than discovering the same problem only
  after every Lesson is placed. H8 is therefore added to the real-time
  constraint list via `build_real_time_constraints(..., include_teacher_
  workload=True)`, using the exact same generic `validate(hypothetical)`
  mechanism as H1-H6/H9/H11/H12 -- no special-cased "workload check"
  exists anywhere in this module.
- H7 ("exactly N lessons for this requirement") remains impossible to
  check per-candidate for the same mathematical reason as before: every
  in-progress state where a requirement isn't finished yet necessarily has
  actual_count < target, which is indistinguishable from a genuine
  shortfall until the LAST lesson for that requirement is placed. It stays
  a whole-batch, post-hoc-only check, run once after the search succeeds.
"""

import time
from dataclasses import dataclass, replace
from typing import Literal

from scheduling_engine.algorithms.resources import (
    LessonFailure,
    SchedulingResources,
    build_lookup_tables,
    build_real_time_constraints,
    candidate_room_ids,
    candidate_teacher_ids,
    no_candidate_teacher_violation,
)
from scheduling_engine.constraints.base import ConstraintViolation
from scheduling_engine.constraints.weekly_periods import WeeklyPeriodsConstraint
from scheduling_engine.models.domain import LessonAssignment
from scheduling_engine.state import SchedulingState

__all__ = [
    "SchedulingResources",
    "LessonFailure",
    "BacktrackingResult",
    "schedule_backtracking",
]

FailureType = Literal["DEFINITELY_INFEASIBLE", "SEARCH_LIMIT_EXCEEDED", "TIMEOUT"]


@dataclass
class BacktrackingResult:
    """success=False -> state is None (same atomicity guarantee as
    GreedyResult: never expose a partial/abandoned search as a usable
    result).

    failure_type distinguishes WHY the search didn't produce a schedule:
    - "DEFINITELY_INFEASIBLE": the search space was FULLY exhausted (every
      candidate of every Lesson, in every combination) with no solution
      found, OR a Lesson has zero candidates at all before the search even
      starts (see lesson_failures). This is a certain answer, not a guess.
    - "SEARCH_LIMIT_EXCEEDED": max_backtrack_steps backtracks were already
      spent and one more would have been needed, before the search could
      finish either way (max_backtrack_steps=0 means zero backtracks are
      permitted at all -- the first one that would be needed aborts the
      search instead of happening). NOT the same claim as infeasibility --
      a solution may exist but wasn't found in the allotted search effort.
    - "TIMEOUT": timeout_seconds elapsed before the search could finish.
      Same caveat as SEARCH_LIMIT_EXCEEDED: not a claim of infeasibility.
    failure_type is None on success, and also None in the one further
    failure case that isn't a search-level outcome at all: every Lesson
    got a valid placement, but the finished schedule still fails the
    post-hoc H7 check (see post_hoc_violations) -- a Lessons-vs-
    requirement_periods data mismatch, not a property of the search.

    lesson_failures is populated only for the pre-flight case (some Lesson
    has no candidate teacher at all -- a static fact, checkable without
    searching). It is intentionally left empty when DEFINITELY_INFEASIBLE
    comes from exhausting the search instead: which combination of choices
    doesn't work is an emergent property of the whole search tree, not
    attributable to one specific Lesson, and reporting one would be
    misleading. backtrack_count is the honest signal for that case.
    """

    success: bool
    state: SchedulingState | None
    failure_type: FailureType | None
    lesson_failures: list[LessonFailure]
    post_hoc_violations: list[ConstraintViolation]
    backtrack_count: int


def schedule_backtracking(
    lessons: list[LessonAssignment],
    resources: SchedulingResources,
    max_backtrack_steps: int = 1000,
    timeout_seconds: float | None = None,
) -> BacktrackingResult:
    tables = build_lookup_tables(resources)
    real_time_constraints = build_real_time_constraints(
        resources, include_teacher_workload=True
    )

    # MRV ordering -- identical rule to Greedy, computed once up front and
    # never revisited: backtracking changes WHICH CANDIDATE is tried at a
    # position, never the order of positions themselves.
    ordered_lessons = sorted(
        lessons,
        key=lambda lesson: len(candidate_teacher_ids(lesson, tables)),
    )
    total = len(ordered_lessons)

    # Pre-flight: any Lesson with zero raw teacher candidates makes the
    # whole thing trivially infeasible -- no point starting a search.
    trivial_failures = [
        LessonFailure(
            lesson_id=lesson.lesson_id,
            class_subject_requirement_id=lesson.class_subject_requirement_id,
            reasons=[no_candidate_teacher_violation(lesson)],
        )
        for lesson in ordered_lessons
        if not candidate_teacher_ids(lesson, tables)
    ]
    if trivial_failures:
        return BacktrackingResult(
            success=False,
            state=None,
            failure_type="DEFINITELY_INFEASIBLE",
            lesson_failures=trivial_failures,
            post_hoc_violations=[],
            backtrack_count=0,
        )

    # Each position's static candidate pool (teacher x time_slot x room) --
    # fixed regardless of search state, computed once.
    candidate_pools: list[list[LessonAssignment]] = [
        [
            replace(lesson, teacher_id=teacher_id, time_slot_id=slot_id, room_id=room_id)
            for teacher_id in candidate_teacher_ids(lesson, tables)
            for slot_id in resources.time_slot_ids
            for room_id in candidate_room_ids(lesson, tables)
        ]
        for lesson in ordered_lessons
    ]

    state = SchedulingState()
    # cursor[i]: index into candidate_pools[i] of the NEXT candidate to try
    # there. committed[i]: the LessonAssignment actually placed at
    # position i right now, or None if nothing is committed there yet.
    cursor = [0] * total
    committed: list[LessonAssignment | None] = [None] * total

    backtrack_count = 0
    start_time = time.monotonic()
    position = 0

    while 0 <= position < total:
        if timeout_seconds is not None and (
            time.monotonic() - start_time > timeout_seconds
        ):
            return BacktrackingResult(
                success=False,
                state=None,
                failure_type="TIMEOUT",
                lesson_failures=[],
                post_hoc_violations=[],
                backtrack_count=backtrack_count,
            )

        pool = candidate_pools[position]
        found = False
        while cursor[position] < len(pool):
            candidate = pool[cursor[position]]
            cursor[position] += 1
            hypothetical = [*state.assignments, candidate]
            if all(c.validate(hypothetical) for c in real_time_constraints):
                state.add_assignment(candidate)
                committed[position] = candidate
                found = True
                break

        if found:
            position += 1
            if position < total:
                cursor[position] = 0
        else:
            # This position's candidates are exhausted. Backtracking means
            # retracting the PREVIOUS position's commitment -- unless we're
            # already at position 0, in which case there is nothing left
            # to retract into and the search space is exhausted (this
            # terminal step is not itself counted as a "backtrack": there
            # is no budget decision to make when giving up for good).
            cursor[position] = 0
            if position == 0:
                position = -1
                break

            # About to perform backtrack number (backtrack_count + 1).
            # "max_backtrack_steps=N" means exactly N backtracks are
            # allowed to actually happen; the (N+1)th is refused BEFORE
            # any state is mutated, so max_backtrack_steps=0 permits zero
            # backtracks -- not one "free" one.
            if backtrack_count >= max_backtrack_steps:
                return BacktrackingResult(
                    success=False,
                    state=None,
                    failure_type="SEARCH_LIMIT_EXCEEDED",
                    lesson_failures=[],
                    post_hoc_violations=[],
                    backtrack_count=backtrack_count,
                )

            position -= 1
            state.remove_last_assignment()
            committed[position] = None
            backtrack_count += 1

    if position < 0:
        return BacktrackingResult(
            success=False,
            state=None,
            failure_type="DEFINITELY_INFEASIBLE",
            lesson_failures=[],
            post_hoc_violations=[],
            backtrack_count=backtrack_count,
        )

    # Every position filled -- the whole-batch H7 check (H8 is already
    # enforced in real time above, so it is never re-checked here).
    weekly_periods_constraint = WeeklyPeriodsConstraint(resources.requirement_periods)
    post_hoc_violations = weekly_periods_constraint.explain_violations(
        state.assignments
    )
    if post_hoc_violations:
        return BacktrackingResult(
            success=False,
            state=None,
            failure_type=None,
            lesson_failures=[],
            post_hoc_violations=post_hoc_violations,
            backtrack_count=backtrack_count,
        )

    return BacktrackingResult(
        success=True,
        state=state,
        failure_type=None,
        lesson_failures=[],
        post_hoc_violations=[],
        backtrack_count=backtrack_count,
    )
