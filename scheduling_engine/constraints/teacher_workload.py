from collections import defaultdict

from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment, TeacherWorkloadLimit


class TeacherWorkloadConstraint(BaseConstraint):
    """H8 Teacher Maximum Workload: a teacher's total scheduled periods must
    not exceed their max_weekly_periods.

    Like H7, this is a whole-batch property -- a teacher's total count can
    only be known from the complete assignment list. See greedy.py's module
    docstring for the fuller discussion of why H7/H8 are both checked once,
    at the end, rather than per-candidate during the search.
    """

    VIOLATION_TYPE = "H8_TEACHER_MAX_WORKLOAD"

    def __init__(self, teachers: list[TeacherWorkloadLimit]) -> None:
        self._max_by_teacher: dict[int, int] = {
            teacher.teacher_id: teacher.max_weekly_periods for teacher in teachers
        }

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        counts: dict[int, int] = defaultdict(int)
        for assignment in assignments:
            if assignment.teacher_id is not None:
                counts[assignment.teacher_id] += 1

        violations: list[ConstraintViolation] = []
        for teacher_id, count in counts.items():
            max_periods = self._max_by_teacher.get(teacher_id)
            if max_periods is None:
                # No known limit for this teacher -- nothing to compare
                # against, so don't guess (same stance as H9/H11's
                # unknown-data handling).
                continue
            if count <= max_periods:
                continue
            violations.append(
                ConstraintViolation(
                    type=self.VIOLATION_TYPE,
                    severity=Severity.ERROR,
                    lesson_id=None,
                    teacher_id=teacher_id,
                    class_id=None,
                    subject_id=None,
                    time_slot_id=None,
                    room_id=None,
                    message=(
                        f"Teacher {teacher_id} has {count} lessons "
                        f"scheduled, exceeding their max of {max_periods}."
                    ),
                    suggested_action=(
                        "Reassign some of this teacher's lessons to "
                        "another teacher."
                    ),
                )
            )
        return violations
