from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ScheduleVersionBase(BaseModel):
    semester_id: int
    version_number: int
    status: Literal["DRAFT", "PUBLISHED"]


class ScheduleVersionCreate(ScheduleVersionBase):
    pass


class ScheduleVersionRead(ScheduleVersionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduleVersionUpdate(BaseModel):
    semester_id: int | None = None
    version_number: int | None = None
    status: Literal["DRAFT", "PUBLISHED"] | None = None


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
    lessons exist. total_lesson_count is the actual total the version's
    semester has after this call -- the number a caller actually wants when
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
