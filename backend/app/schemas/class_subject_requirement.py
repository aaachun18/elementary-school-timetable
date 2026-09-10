from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClassSubjectRequirementBase(BaseModel):
    semester_id: int
    class_id: int
    subject_id: int
    weekly_periods: int
    required_teacher_id: int | None = None
    required_room_type: str | None = None
    consecutive_limit: int | None = None


class ClassSubjectRequirementCreate(ClassSubjectRequirementBase):
    pass


class ClassSubjectRequirementRead(ClassSubjectRequirementBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassSubjectRequirementUpdate(BaseModel):
    semester_id: int | None = None
    class_id: int | None = None
    subject_id: int | None = None
    weekly_periods: int | None = None
    required_teacher_id: int | None = None
    required_room_type: str | None = None
    consecutive_limit: int | None = None
