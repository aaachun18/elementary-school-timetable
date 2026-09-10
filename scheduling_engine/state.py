"""Mutable scheduling state the Greedy/Backtracking algorithms build up one
assignment at a time. Framework-independent, like everything else under
scheduling_engine/ -- see AGENTS.md section 4."""

from dataclasses import dataclass, field

from scheduling_engine.models.domain import LessonAssignment


@dataclass
class SchedulingState:
    """Not frozen (unlike the domain dataclasses) -- this is the one
    genuinely mutable object in the engine, since Greedy/Backtracking need
    to build a schedule up incrementally.

    count_teacher_periods()/count_requirement_lessons() are computed live
    from `assignments` on every call rather than cached in separate running
    counters. This costs an O(n) scan per call instead of O(1), but it
    means there is exactly one source of truth: a counter that has to be
    remembered to increment/decrement in step with `assignments` is a
    classic place for state to quietly drift out of sync -- especially
    once Backtracking (a later Task) starts removing assignments again,
    which would require every counter to also have correct decrement
    logic. At this project's scale, the O(n) scan is not a real cost.
    """

    assignments: list[LessonAssignment] = field(default_factory=list)

    def add_assignment(self, assignment: LessonAssignment) -> None:
        self.assignments.append(assignment)

    def remove_last_assignment(self) -> LessonAssignment:
        """Undo the most recent add_assignment() call. Used by
        Backtracking to retract a commitment when a later Lesson turns out
        to have no valid candidate -- this is exactly why `assignments` is
        a plain, append-ordered list rather than e.g. a set: the most
        recent addition is always the correct thing to retract, in strict
        LIFO order matching the search's own call stack."""
        return self.assignments.pop()

    def count_teacher_periods(self, teacher_id: int) -> int:
        return sum(1 for a in self.assignments if a.teacher_id == teacher_id)

    def count_requirement_lessons(self, requirement_id: int) -> int:
        return sum(
            1
            for a in self.assignments
            if a.class_subject_requirement_id == requirement_id
        )
