from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import LessonAssignment


class TeacherParticipationConstraint(BaseConstraint):
    """H5 Teacher Participation (Task 98, replaces H5 Teacher
    Qualification): a lesson may only be taught by a teacher taking part
    in the semester's scheduling (SemesterTeacher). The search never tries
    anyone else (candidate_teacher_ids()), so this only ever fires for a
    manual change -- a reassignment or placement naming another teacher --
    whose weekly maximum and unavailable slots the semester doesn't know."""

    VIOLATION_TYPE = "H5_TEACHER_NOT_PARTICIPATING"

    def __init__(self, teacher_ids: list[int]) -> None:
        self._teacher_ids = frozenset(teacher_ids)

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for assignment in assignments:
            if assignment.teacher_id is None or assignment.teacher_id in self._teacher_ids:
                continue
            violations.append(
                ConstraintViolation(
                    type=self.VIOLATION_TYPE,
                    severity=Severity.ERROR,
                    lesson_id=assignment.lesson_id,
                    teacher_id=assignment.teacher_id,
                    class_id=assignment.class_id,
                    subject_id=assignment.subject_id,
                    time_slot_id=assignment.time_slot_id,
                    room_id=assignment.room_id,
                    class_subject_requirement_id=assignment.class_subject_requirement_id,
                    message=(
                        f"Teacher {assignment.teacher_id} teaches lesson "
                        f"{assignment.lesson_id} but does not take part in this "
                        "semester's scheduling."
                    ),
                    suggested_action=(
                        "Add the teacher to this semester's teachers, or assign a "
                        "teacher who takes part."
                    ),
                )
            )
        return violations
