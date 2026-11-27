from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.services.school_structure import SchoolType


class SchoolBase(BaseModel):
    name: str
    is_active: bool = True
    school_type: SchoolType


class SchoolCreate(BaseModel):
    name: str
    # Fixes the school's grades and time slot grid, built with it.
    school_type: SchoolType = SchoolType.ELEMENTARY


class SchoolRead(SchoolBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# school_type is deliberately absent: the grades and time slots built from
# it can't follow a change.
class SchoolUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
