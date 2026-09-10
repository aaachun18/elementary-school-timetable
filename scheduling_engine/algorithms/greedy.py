"""Greedy Scheduler.

For each Lesson (processed in MRV order -- fewest candidate teachers
first), pick the first (teacher, time_slot, room) combination that
satisfies every *real-time* Hard Constraint: H1-H6, H9, H11, H12. If no
Lesson-level candidate exists, the whole run fails atomically -- no partial
schedule is ever returned (see GreedyResult).

Note (Task 20): H8 is deliberately still NOT included in this algorithm's
real-time constraints, unlike Backtracking's. Greedy has no way to recover
from a bad early choice -- there's nothing to backtrack to -- so real-time
H8 filtering would only change WHERE a doomed run fails, not WHETHER it
succeeds. It stays a post-hoc-only check here; see backtracking.py's
module docstring for the fuller H7-vs-H8 discussion and why Backtracking
makes the opposite choice for H8.
"""

from dataclasses import dataclass, replace

from scheduling_engine.algorithms.resources import (
    LessonFailure,
    LookupTables,
    SchedulingResources,
    build_lookup_tables,
    build_real_time_constraints,
    candidate_room_ids,
    candidate_teacher_ids,
    no_candidate_teacher_violation,
)
from scheduling_engine.constraints.base import BaseConstraint, ConstraintViolation
from scheduling_engine.constraints.teacher_workload import TeacherWorkloadConstraint
from scheduling_engine.constraints.weekly_periods import WeeklyPeriodsConstraint
from scheduling_engine.models.domain import LessonAssignment
from scheduling_engine.state import SchedulingState

__all__ = ["SchedulingResources", "LessonFailure", "GreedyResult", "schedule_greedy"]


@dataclass
class GreedyResult:
    """success=False means NO schedule was produced: `state` is None, on
    purpose -- this algorithm never returns a partial result a caller
    might mistake for a usable schedule (the atomicity the Task asks for).

    On failure, exactly one of the two lists is populated:
    - lesson_failures: at least one Lesson had no valid candidate at all
      (a real-time constraint problem). state is None; the run stopped
      committing new assignments, but still attempted every remaining
      Lesson (against whatever was placed before the first failure) so
      this list reports every Lesson that failed, not just the first.
    - post_hoc_violations: every Lesson found a candidate, but the
      finished schedule still fails H7 (wrong lesson count for some
      requirement) or H8 (a teacher over their workload cap).
    """

    success: bool
    state: SchedulingState | None
    lesson_failures: list[LessonFailure]
    post_hoc_violations: list[ConstraintViolation]


def _find_first_valid_candidate(
    lesson: LessonAssignment,
    state: SchedulingState,
    time_slot_ids: list[int],
    real_time_constraints: list[BaseConstraint],
    candidate_teachers: list[int],
    candidate_rooms: list[int | None],
) -> LessonAssignment | None:
    for teacher_id in candidate_teachers:
        for time_slot_id in time_slot_ids:
            for room_id in candidate_rooms:
                candidate = replace(
                    lesson,
                    teacher_id=teacher_id,
                    time_slot_id=time_slot_id,
                    room_id=room_id,
                )
                hypothetical = [*state.assignments, candidate]
                if all(c.validate(hypothetical) for c in real_time_constraints):
                    return candidate
    return None


def _explain_no_valid_candidate(
    lesson: LessonAssignment,
    state: SchedulingState,
    time_slot_ids: list[int],
    real_time_constraints: list[BaseConstraint],
    candidate_teachers: list[int],
    candidate_rooms: list[int | None],
) -> list[ConstraintViolation]:
    """Only called once a Lesson is already known to have no valid
    candidate. Re-tries every combination (the slow path -- fine, since it
    only runs on failure) and collects every distinct violation message
    across all of them, deduplicated by message so the same reason isn't
    repeated once per time-slot/room combination tried with that teacher.
    """
    if not candidate_teachers:
        return [no_candidate_teacher_violation(lesson)]

    seen_messages: set[str] = set()
    reasons: list[ConstraintViolation] = []
    for teacher_id in candidate_teachers:
        for time_slot_id in time_slot_ids:
            for room_id in candidate_rooms:
                candidate = replace(
                    lesson,
                    teacher_id=teacher_id,
                    time_slot_id=time_slot_id,
                    room_id=room_id,
                )
                hypothetical = [*state.assignments, candidate]
                for constraint in real_time_constraints:
                    for violation in constraint.explain_violations(hypothetical):
                        if violation.message in seen_messages:
                            continue
                        seen_messages.add(violation.message)
                        reasons.append(violation)
    return reasons


def schedule_greedy(
    lessons: list[LessonAssignment],
    resources: SchedulingResources,
    state: SchedulingState | None = None,
) -> GreedyResult:
    """Entry point.

    `lessons` is the to-do list: each one a LessonAssignment with
    teacher_id/time_slot_id/room_id all None (an unplaced lesson). Reusing
    LessonAssignment itself for "not yet assigned" rather than inventing a
    second, near-identical dataclass matches how a real Schedule row can
    already look before every part of it is filled in.

    `state` lets a caller seed the search with assignments that already
    exist; defaults to an empty SchedulingState.
    """
    working_state = state if state is not None else SchedulingState()
    tables: LookupTables = build_lookup_tables(resources)
    real_time_constraints = build_real_time_constraints(resources)

    # MRV: process the Lesson with the fewest candidate teachers first. A
    # required teacher (H6) pins the candidate count to exactly 1, so
    # those Lessons always sort to the front.
    ordered_lessons = sorted(
        lessons,
        key=lambda lesson: len(candidate_teacher_ids(lesson, tables)),
    )

    lesson_failures: list[LessonFailure] = []

    for lesson in ordered_lessons:
        candidate_teachers = candidate_teacher_ids(lesson, tables)
        candidate_rooms = candidate_room_ids(lesson, tables)

        candidate = _find_first_valid_candidate(
            lesson,
            working_state,
            resources.time_slot_ids,
            real_time_constraints,
            candidate_teachers,
            candidate_rooms,
        )

        if candidate is not None:
            working_state.add_assignment(candidate)
        else:
            reasons = _explain_no_valid_candidate(
                lesson,
                working_state,
                resources.time_slot_ids,
                real_time_constraints,
                candidate_teachers,
                candidate_rooms,
            )
            lesson_failures.append(
                LessonFailure(
                    lesson_id=lesson.lesson_id,
                    class_subject_requirement_id=lesson.class_subject_requirement_id,
                    reasons=reasons,
                )
            )

    if lesson_failures:
        return GreedyResult(
            success=False,
            state=None,
            lesson_failures=lesson_failures,
            post_hoc_violations=[],
        )

    # Every Lesson placed -- now the whole-batch H7/H8 checks.
    weekly_periods_constraint = WeeklyPeriodsConstraint(resources.requirement_periods)
    workload_constraint = TeacherWorkloadConstraint(resources.teacher_workload_limits)
    post_hoc_violations = weekly_periods_constraint.explain_violations(
        working_state.assignments
    ) + workload_constraint.explain_violations(working_state.assignments)

    if post_hoc_violations:
        return GreedyResult(
            success=False,
            state=None,
            lesson_failures=[],
            post_hoc_violations=post_hoc_violations,
        )

    return GreedyResult(
        success=True,
        state=working_state,
        lesson_failures=[],
        post_hoc_violations=[],
    )
