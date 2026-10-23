from datetime import datetime

from pydantic import BaseModel, Field

# 共同排課 (併班上課) of one 排課紀錄 -- see app/models/combined_lesson.py.

MIN_MEMBERS = 2


class CombinedLessonFields(BaseModel):
    """What the wizard's 共同排課 dialog sets. requirement_ids: the class
    subject requirements taught together, the one that started the merge
    first. Without a lesson pattern, merged_count says how many of their
    lessons are merged; with one, block_nos says which whole blocks (and
    merged_count is ignored). room_id: a school room, or None for the
    原班教室 of homeroom_class_id (a member's class; default: the first
    member's)."""

    requirement_ids: list[int] = Field(min_length=MIN_MEMBERS)
    merged_count: int | None = Field(default=None, ge=1)
    block_nos: list[int] | None = None
    room_id: int | None = None
    homeroom_class_id: int | None = None


class CombinedLessonCreate(CombinedLessonFields):
    schedule_version_id: int


class CombinedLessonUpdate(CombinedLessonFields):
    pass


class CombinedInstanceRead(BaseModel):
    """One 合併節: per member (in requirement_ids order) its lessons of it,
    in period order. Empty until the record's lessons exist."""

    key: str
    member_lesson_ids: list[list[int]]


class CombinedLessonRead(BaseModel):
    id: int
    schedule_version_id: int
    requirement_ids: list[int]
    merged_count: int
    block_nos: list[int] | None
    room_id: int | None
    homeroom_class_id: int | None
    instances: list[CombinedInstanceRead]
    created_at: datetime
    updated_at: datetime
