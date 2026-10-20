from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.services.grade_levels import check_grade_level


class GradeBase(BaseModel):
    name: str
    level: int


class GradeCreate(GradeBase):
    # Task 98: 422 with a Chinese message instead of the database CHECK's 409.
    @field_validator("level")
    @classmethod
    def _level_valid(cls, value: int) -> int:
        check_grade_level(value)
        return value


class GradeRead(GradeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GradeUpdate(BaseModel):
    name: str | None = None
    level: int | None = None

    @field_validator("level")
    @classmethod
    def _level_valid(cls, value: int | None) -> int | None:
        return check_grade_level(value)
