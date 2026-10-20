from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.teacher_periods import (
    NEGATIVE_MAX_MESSAGE,
    NEGATIVE_MIN_MESSAGE,
    check_not_negative,
    check_periods_range,
)

# Task 98: one semester's scheduling settings (the wizard's steps 4-6 and
# 8): which teachers take part, their weekly periods range and unavailable
# slots, and the slots each grade is open for.

DUPLICATE_TEACHER_MESSAGE = "同一位教師只能出現一次"
EMPTY_GRADE_SLOTS_MESSAGE = "每個年級至少要開放一個可排節次"


class SemesterTeacherEntry(BaseModel):
    teacher_id: int
    min_weekly_periods: int
    max_weekly_periods: int
    unavailable_time_slot_ids: list[int] = Field(default_factory=list)

    @field_validator("min_weekly_periods")
    @classmethod
    def _min_not_negative(cls, value: int) -> int:
        check_not_negative(value, NEGATIVE_MIN_MESSAGE)
        return value

    @field_validator("max_weekly_periods")
    @classmethod
    def _max_not_negative(cls, value: int) -> int:
        check_not_negative(value, NEGATIVE_MAX_MESSAGE)
        return value

    @model_validator(mode="after")
    def _min_not_above_max(self) -> "SemesterTeacherEntry":
        check_periods_range(self.min_weekly_periods, self.max_weekly_periods)
        return self


class SemesterTeachersUpdate(BaseModel):
    """PUT /semesters/{id}/teachers: the complete list -- a teacher left
    out no longer takes part in the semester."""

    teachers: list[SemesterTeacherEntry]

    @model_validator(mode="after")
    def _each_teacher_once(self) -> "SemesterTeachersUpdate":
        teacher_ids = [entry.teacher_id for entry in self.teachers]
        if len(teacher_ids) != len(set(teacher_ids)):
            raise ValueError(DUPLICATE_TEACHER_MESSAGE)
        return self


class SemesterTeacherRead(BaseModel):
    teacher_id: int
    teacher_name: str
    min_weekly_periods: int
    max_weekly_periods: int
    unavailable_time_slot_ids: list[int]


class GradeTimeSlotsUpdate(BaseModel):
    """PUT /semesters/{id}/grades/{grade_id}/time-slots: every slot the
    grade is open for (replaces the previous set)."""

    time_slot_ids: list[int]

    @field_validator("time_slot_ids")
    @classmethod
    def _not_empty(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError(EMPTY_GRADE_SLOTS_MESSAGE)
        return sorted(set(value))


class GradeTimeSlotsRead(BaseModel):
    grade_id: int
    time_slot_ids: list[int]
