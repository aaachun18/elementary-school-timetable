"""Task 88: TeacherMinWorkloadConstraint -- a WARNING when a teacher has
fewer rows than their min_weekly_periods; None means no minimum. Pure
Python, no database."""

from scheduling_engine.constraints.base import Severity
from scheduling_engine.constraints.teacher_min_workload import TeacherMinWorkloadConstraint
from scheduling_engine.models.domain import LessonAssignment, TeacherMinimumWorkload


def _rows(teacher_id: int | None, count: int, first_lesson_id: int = 1) -> list[LessonAssignment]:
    return [
        LessonAssignment(
            lesson_id=first_lesson_id + n,
            class_subject_requirement_id=1,
            class_id=1,
            subject_id=1,
            teacher_id=teacher_id,
            time_slot_id=n + 1,
            room_id=None,
        )
        for n in range(count)
    ]


def _check(minimum: int | None, rows: list[LessonAssignment]) -> list[tuple[str, int | None]]:
    rule = TeacherMinWorkloadConstraint([TeacherMinimumWorkload(teacher_id=7, min_weekly_periods=minimum)])
    return [(v.type, v.teacher_id) for v in rule.explain_violations(rows)]


def test_below_minimum_is_a_warning() -> None:
    rule = TeacherMinWorkloadConstraint([TeacherMinimumWorkload(teacher_id=7, min_weekly_periods=3)])

    [violation] = rule.explain_violations(_rows(7, 2))

    assert violation.type == "TEACHER_MIN_WORKLOAD"
    assert violation.severity is Severity.WARNING
    assert violation.teacher_id == 7
    assert violation.identity_key == "TEACHER_MIN_WORKLOAD:7"


def test_at_or_above_minimum_is_fine() -> None:
    assert _check(3, _rows(7, 3)) == []
    assert _check(3, _rows(7, 4)) == []


def test_none_means_no_minimum() -> None:
    assert _check(None, []) == []


def test_zero_minimum_is_never_undershot() -> None:
    assert _check(0, []) == []


def test_no_rows_count_as_zero_and_other_teachers_do_not_count() -> None:
    rows = _rows(8, 5) + _rows(None, 2, first_lesson_id=10)

    assert _check(1, rows) == [("TEACHER_MIN_WORKLOAD", 7)]
