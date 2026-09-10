from collections import defaultdict

from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment, RequirementPeriods


class WeeklyPeriodsConstraint(BaseConstraint):
    """H7 Weekly Subject Requirement: every ClassSubjectRequirement must end
    up with exactly `weekly_periods` scheduled lessons -- no more, no
    fewer.

    Unlike H1-H6/H9/H11/H12 (each of which flags a *specific* offending
    assignment, or an offending pair of them), this is inherently a
    whole-batch property: whether a requirement's count is right cannot be
    known from any one assignment, or even a subset -- only from every
    assignment that exists. The interface is still `explain_violations(
    assignments: list[LessonAssignment])`, identical to every other
    constraint (so a caller can drive H1 through H12 uniformly, without
    needing to know which ones are per-assignment and which are
    whole-batch) -- but it must always be called with the COMPLETE, final
    list, e.g. `state.assignments` from a finished SchedulingState, never a
    partial slice. See greedy.py for why this is checked once, after every
    Lesson has been placed, rather than per-candidate.
    """

    VIOLATION_TYPE = "H7_WEEKLY_PERIODS"

    def __init__(self, requirements: list[RequirementPeriods]) -> None:
        self._target_by_requirement: dict[int, int] = {
            requirement.class_subject_requirement_id: requirement.weekly_periods
            for requirement in requirements
        }

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        actual_counts: dict[int, int] = defaultdict(int)
        for assignment in assignments:
            actual_counts[assignment.class_subject_requirement_id] += 1

        violations: list[ConstraintViolation] = []
        for requirement_id, target in self._target_by_requirement.items():
            actual = actual_counts.get(requirement_id, 0)
            if actual == target:
                continue
            violations.append(
                ConstraintViolation(
                    type=self.VIOLATION_TYPE,
                    severity=Severity.ERROR,
                    lesson_id=None,
                    teacher_id=None,
                    class_id=None,
                    subject_id=None,
                    time_slot_id=None,
                    room_id=None,
                    class_subject_requirement_id=requirement_id,
                    message=(
                        f"Requirement {requirement_id} needs {target} "
                        f"scheduled lessons but has {actual}."
                    ),
                    suggested_action=(
                        "Schedule the missing lessons for this requirement."
                        if actual < target
                        else "Remove the extra scheduled lessons for this "
                        "requirement."
                    ),
                )
            )
        return violations
