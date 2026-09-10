from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SchoolBase(BaseModel):
    name: str
    is_active: bool = True


class SchoolCreate(BaseModel):
    name: str


class SchoolRead(SchoolBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SchoolUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
