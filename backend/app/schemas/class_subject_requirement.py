from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.lesson_pattern import check_pattern_total, normalize_lesson_pattern
from app.services.requirement_rules import check_weekly_periods

CONSECUTIVE_LIMIT_DESCRIPTION = "已停用：不再被任何排課規則使用，請改用 lesson_pattern（連堂樣式）"
LESSON_PATTERN_DESCRIPTION = (
    "連堂樣式，例如 2+1：每週節數拆成幾組連堂，每組 1 到 3 節，各組節數總和等於每週節數；"
    "同一組排在同一天相鄰的教學時段，不同組排在不同天。存成由大到小的寫法（1+2 會存成 2+1）。"
    "空值表示不指定連堂"
)


class ClassSubjectRequirementBase(BaseModel):
    # v3: the 排課紀錄 whose settings this requirement is part of.
    schedule_version_id: int
    class_id: int
    subject_id: int
    weekly_periods: int
    required_teacher_id: int | None = None
    # Task 98: the one special room (None: 原班教室). Replaces
    # required_room_type, which the API no longer takes -- rooms have no
    # types any more.
    required_room_id: int | None = None
    # Deprecated since Task 87 (kept for compatibility; nothing reads it).
    consecutive_limit: int | None = Field(
        default=None, deprecated=True, description=CONSECUTIVE_LIMIT_DESCRIPTION
    )
    lesson_pattern: str | None = Field(default=None, description=LESSON_PATTERN_DESCRIPTION)


def _normalize(value: str | None) -> str | None:
    # ValueError -> FastAPI's 422, with the Chinese message.
    return normalize_lesson_pattern(value)


def _weekly_periods(value: int | None) -> int | None:
    # Task 98: 1-6 periods a week (ValueError -> 422, Chinese message).
    return check_weekly_periods(value)


class ClassSubjectRequirementCreate(ClassSubjectRequirementBase):
    _normalize_pattern = field_validator("lesson_pattern")(_normalize)
    _check_weekly_periods = field_validator("weekly_periods")(_weekly_periods)

    @model_validator(mode="after")
    def _pattern_matches_weekly_periods(self) -> "ClassSubjectRequirementCreate":
        check_pattern_total(self.lesson_pattern, self.weekly_periods)
        return self


class ClassSubjectRequirementRead(ClassSubjectRequirementBase):
    id: int
    created_at: datetime
    updated_at: datetime
    # Task 73 / v3: computed per request, not a column -- whether the
    # requirement's record is no longer 尚未排課 (then PATCH/DELETE are
    # refused with 409). Response-only: a request carrying it is simply
    # ignored (pydantic drops unknown fields).
    is_locked: bool

    model_config = ConfigDict(from_attributes=True)


class ClassSubjectRequirementUpdate(BaseModel):
    # The record is fixed: a requirement never moves to another record.
    class_id: int | None = None
    subject_id: int | None = None
    weekly_periods: int | None = None
    required_teacher_id: int | None = None
    # Task 98: the one special room (None: 原班教室). Replaces
    # required_room_type, which the API no longer takes -- rooms have no
    # types any more.
    required_room_id: int | None = None
    consecutive_limit: int | None = Field(
        default=None, deprecated=True, description=CONSECUTIVE_LIMIT_DESCRIPTION
    )
    # Task 87: checked against the RESULTING weekly_periods in the service
    # (an update may change either one).
    lesson_pattern: str | None = Field(default=None, description=LESSON_PATTERN_DESCRIPTION)

    _normalize_pattern = field_validator("lesson_pattern")(_normalize)
    _check_weekly_periods = field_validator("weekly_periods")(_weekly_periods)


class RequirementSyncRequest(BaseModel):
    schedule_version_id: int


class SkippedSubject(BaseModel):
    id: int
    name: str


class RequirementSyncResult(BaseModel):
    """POST /class-subject-requirements/sync: what copying the school's
    科目需求 into the (尚未排課) record changed."""

    created: int
    updated: int
    removed: int
    # 停用的科目 with a 年級科目需求 that applies to a class: left out of
    # the record (the school's rule itself stays; 啟用 brings it back on the
    # next sync). Sorted by name.
    skipped_subjects: list[SkippedSubject] = []
