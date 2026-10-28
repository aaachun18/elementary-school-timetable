from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.schedule_version import NOTE_MAX_LENGTH


# v3 status values -- see app/models/schedule_version.py.
VersionStatus = Literal["NOT_SCHEDULED", "AUTO", "MANUAL", "COPIED", "EDITING"]


class ScheduleVersionCreate(BaseModel):
    """A new 排課紀錄 is always 尚未排課, numbered by the school's next
    編號 -- 開始排課 creates one, then fills its settings step by step."""

    semester_id: int


class ScheduleVersionRead(BaseModel):
    id: int
    semester_id: int
    # The record's permanent serial; None only for a manual edit's working
    # copy (EDITING).
    version_number: int | None
    # 編號 as 排課紀錄 shows it: 1 = the school's newest record (see
    # app/models/schedule_version.py). None for a working copy.
    display_number: int | None
    status: VersionStatus
    is_published: bool
    # COPIED: the source's serial, and its 編號 now (None once the source
    # has been deleted).
    copied_from_number: int | None
    copied_from_display_number: int | None
    editing_source_id: int | None
    note: str | None
    # Task 103: the furthest 開始排課 step reached (None: not recorded yet).
    wizard_furthest_step: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduleVersionUpdate(BaseModel):
    """PATCH: only the 備註 (an empty one is cleared) and, Task 103, the
    furthest 開始排課 step reached change this way. The status changes
    through its own actions (run-scheduler, publish, edit/save)."""

    note: str | None = Field(default=None, max_length=NOTE_MAX_LENGTH)
    # Only ever goes up: a lower value than the stored one is ignored.
    wizard_furthest_step: int | None = Field(default=None, ge=0)

    @field_validator("note")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ScheduleVersionCopyTimetable(BaseModel):
    """Body of POST /schedule-versions/{id}/copy (複製此課表): the semester
    the copy belongs to -- any semester of the source's academic year,
    the source's own included. Omitted: the source's own semester."""

    target_semester_id: int | None = None


# --- generate-lessons (diff sync), not standard CRUD ---


class GeneratedLessonInfo(BaseModel):
    lesson_id: int
    class_subject_requirement_id: int
    sequence_number: int


class GenerateLessonsResult(BaseModel):
    """created_count is how many NEW Lesson rows this call inserted --
    calling generate-lessons again on an already-synced version correctly
    returns created_count=0, that's the diff-sync design working as
    intended (see generate_lessons()'s docstring), not a sign that no
    lessons exist. total_lesson_count is the actual total the record has
    after this call -- the number a caller actually wants when
    asking "how many lessons are there to schedule", which is why a Task
    32.8 bug report found a frontend page conflating created_count with
    that instead."""

    created_lessons: list[GeneratedLessonInfo]
    created_count: int
    total_lesson_count: int


class OverProvisionedRequirement(BaseModel):
    class_subject_requirement_id: int
    weekly_periods: int
    existing_lesson_count: int
