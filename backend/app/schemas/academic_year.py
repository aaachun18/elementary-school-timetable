from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AcademicYearBase(BaseModel):
    year: int
    is_active: bool = True


class AcademicYearCreate(BaseModel):
    year: int


class AcademicYearRead(AcademicYearBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AcademicYearUpdate(BaseModel):
    year: int | None = None
    is_active: bool | None = None
