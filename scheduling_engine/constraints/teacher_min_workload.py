from collections import defaultdict

from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment, TeacherMinimumWorkload


class TeacherMinWorkloadConstraint(BaseConstraint):
    """Task 88: a teacher scheduled for fewer periods than their
    min_weekly_periods -- TEACHER_MIN_WORKLOAD, a WARNING, not a Hard
    Constraint (AGENTS.md's H8 is only the maximum).

    Only the schedule check (backend services/schedule_check.py) runs this;
    no scheduling algorithm and no static pre-check includes it, so it can
    never make a search fail or block anything. Like H8 it is a whole-batch
    count of the rows with a teacher; a teacher with no row at all counts
    as 0. Which teachers are listed is the caller's choice (the check lists
    the active ones). min_weekly_periods None means no minimum; 0 can never
    be undershot.
    """

    VIOLATION_TYPE = "TEACHER_MIN_WORKLOAD"

    def __init__(self, teachers: list[TeacherMinimumWorkload]) -> None:
        self._teachers = teachers

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        counts: dict[int, int] = defaultdict(int)
        for assignment in assignments:
            if assignment.teacher_id is not None:
                counts[assignment.teacher_id] += 1

        violations: list[ConstraintViolation] = []
        for teacher in self._teachers:
            minimum = teacher.min_weekly_periods
            count = counts.get(teacher.teacher_id, 0)
            if minimum is None or count >= minimum:
                continue
            violations.append(
                ConstraintViolation(
                    type=self.VIOLATION_TYPE,
                    severity=Severity.WARNING,
                    lesson_id=None,
                    teacher_id=teacher.teacher_id,
                    class_id=None,
                    subject_id=None,
                    time_slot_id=None,
                    room_id=None,
                    message=(
                        f"Teacher {teacher.teacher_id} has {count} lessons "
                        f"scheduled, below their minimum of {minimum}."
                    ),
                    suggested_action=(
                        "Assign more lessons to this teacher, or lower their "
                        "minimum weekly periods."
                    ),
                    identity_key=f"{self.VIOLATION_TYPE}:{teacher.teacher_id}",
                )
            )
        return violations
