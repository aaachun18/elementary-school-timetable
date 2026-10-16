from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.lesson_pattern import check_pattern_total, normalize_lesson_pattern

CONSECUTIVE_LIMIT_DESCRIPTION = "已停用：不再被任何排課規則使用，請改用 lesson_pattern（連堂樣式）"
LESSON_PATTERN_DESCRIPTION = (
    "連堂樣式，例如 2+1：每週節數拆成幾組連堂，每組 1 到 3 節，各組節數總和等於每週節數；"
    "同一組排在同一天相鄰的教學時段，不同組排在不同天。存成由大到小的寫法（1+2 會存成 2+1）。"
    "空值表示不指定連堂"
)


class ClassSubjectRequirementBase(BaseModel):
    semester_id: int
    class_id: int
    subject_id: int
    weekly_periods: int
    required_teacher_id: int | None = None
    required_room_type: str | None = None
    # Deprecated since Task 87 (kept for compatibility; nothing reads it).
    consecutive_limit: int | None = Field(
        default=None, deprecated=True, description=CONSECUTIVE_LIMIT_DESCRIPTION
    )
    lesson_pattern: str | None = Field(default=None, description=LESSON_PATTERN_DESCRIPTION)


def _normalize(value: str | None) -> str | None:
    # ValueError -> FastAPI's 422, with the Chinese message.
    return normalize_lesson_pattern(value)


class ClassSubjectRequirementCreate(ClassSubjectRequirementBase):
    _normalize_pattern = field_validator("lesson_pattern")(_normalize)

    @model_validator(mode="after")
    def _pattern_matches_weekly_periods(self) -> "ClassSubjectRequirementCreate":
        check_pattern_total(self.lesson_pattern, self.weekly_periods)
        return self


class ClassSubjectRequirementRead(ClassSubjectRequirementBase):
    id: int
    created_at: datetime
    updated_at: datetime
    # Task 73: computed per request, not a column -- whether a PUBLISHED or
    # ARCHIVED version uses this requirement's lessons (then PATCH/DELETE
    # are refused with 409). Response-only: it is not in Create/Update, so a
    # request carrying it is simply ignored (pydantic drops unknown fields).
    is_locked: bool

    model_config = ConfigDict(from_attributes=True)


class ClassSubjectRequirementUpdate(BaseModel):
    semester_id: int | None = None
    class_id: int | None = None
    subject_id: int | None = None
    weekly_periods: int | None = None
    required_teacher_id: int | None = None
    required_room_type: str | None = None
    consecutive_limit: int | None = Field(
        default=None, deprecated=True, description=CONSECUTIVE_LIMIT_DESCRIPTION
    )
    # Task 87: checked against the RESULTING weekly_periods in the service
    # (an update may change either one).
    lesson_pattern: str | None = Field(default=None, description=LESSON_PATTERN_DESCRIPTION)

    _normalize_pattern = field_validator("lesson_pattern")(_normalize)
