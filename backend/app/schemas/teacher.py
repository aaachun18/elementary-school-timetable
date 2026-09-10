from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TeacherBase(BaseModel):
    name: str
    is_active: bool = True
    min_weekly_periods: int
    max_weekly_periods: int


class TeacherCreate(BaseModel):
    name: str
    min_weekly_periods: int
    max_weekly_periods: int


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


# --- Semantic sub-resource request bodies (not standalone CRUD schemas) ---


class TeacherSubjectCreate(BaseModel):
    subject_id: int


class TeacherAvailabilityCreate(BaseModel):
    time_slot_id: int
