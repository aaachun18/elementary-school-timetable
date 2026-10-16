from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.services.teacher_periods import (
    NEGATIVE_MAX_MESSAGE,
    NEGATIVE_MIN_MESSAGE,
    check_not_negative,
    check_periods_range,
)


class TeacherBase(BaseModel):
    name: str
    is_active: bool = True
    min_weekly_periods: int
    max_weekly_periods: int


class TeacherCreate(BaseModel):
    name: str
    min_weekly_periods: int
    max_weekly_periods: int

    # Task 88: 422 with a Chinese message instead of the database CHECK's
    # 409 (min <= max) -- and neither may be negative, which nothing
    # checked before.
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
    def _min_not_above_max(self) -> "TeacherCreate":
        check_periods_range(self.min_weekly_periods, self.max_weekly_periods)
        return self


class TeacherRead(TeacherBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeacherUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    min_weekly_periods: int | None = None
    max_weekly_periods: int | None = None

    # Task 88: min <= max is checked by the service against the values the
    # update leaves behind (one of them may come from the stored row).
    @field_validator("min_weekly_periods")
    @classmethod
    def _min_not_negative(cls, value: int | None) -> int | None:
        return check_not_negative(value, NEGATIVE_MIN_MESSAGE)

    @field_validator("max_weekly_periods")
    @classmethod
    def _max_not_negative(cls, value: int | None) -> int | None:
        return check_not_negative(value, NEGATIVE_MAX_MESSAGE)


# --- Semantic sub-resource request bodies (not standalone CRUD schemas) ---


class TeacherSubjectCreate(BaseModel):
    subject_id: int


class TeacherAvailabilityCreate(BaseModel):
    time_slot_id: int
