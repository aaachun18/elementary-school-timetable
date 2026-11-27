from scheduling_engine.constraints.base import (
    BaseConstraint,
    ConstraintViolation,
    Severity,
)
from scheduling_engine.models.domain import CombinedLesson, LessonAssignment


class CombinedLessonConstraint(BaseConstraint):
    """共同排課 (H14 Combined Lesson): the lessons of one 合併節 are taught
    together -- lesson i of every member in the same time slot. A member
    lesson with no time slot yet (or no row at all) is not compared; the
    search always places a 合併節 as one, so only a stored timetable can
    break this (the schedule check reports it)."""

    VIOLATION_TYPE = "H14_COMBINED_LESSON_SPLIT"

    def __init__(self, combined_lessons: list[CombinedLesson]) -> None:
        self._combined_lessons = combined_lessons

    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        by_lesson = {assignment.lesson_id: assignment for assignment in assignments}
        violations: list[ConstraintViolation] = []
        for combined in self._combined_lessons:
            size = min(len(lesson_ids) for lesson_ids in combined.member_lesson_ids)
            for index in range(size):
                placed = [
                    by_lesson[lesson_ids[index]]
                    for lesson_ids in combined.member_lesson_ids
                    if lesson_ids[index] in by_lesson
                    and by_lesson[lesson_ids[index]].time_slot_id is not None
                ]
                if len({assignment.time_slot_id for assignment in placed}) <= 1:
                    continue
                for assignment in placed:
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
                            message="共同排課的課被拆開了：合併的各班這一節必須排在同一個時段",
                            suggested_action="把合併的各班這一節移回同一個時段",
                            identity_key=f"{self.VIOLATION_TYPE}:{combined.key}:{index}",
                        )
                    )
        return violations
