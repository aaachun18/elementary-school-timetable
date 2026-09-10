from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SemesterBase(BaseModel):
    academic_year_id: int
    number: int
    is_active: bool = True


class SemesterCreate(BaseModel):
    academic_year_id: int
    number: int


class SemesterRead(SemesterBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SemesterUpdate(BaseModel):
    academic_year_id: int | None = None
    number: int | None = None
    is_active: bool | None = None
