from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubjectBase(BaseModel):
    name: str
    is_active: bool = True


class SubjectCreate(BaseModel):
    name: str


class SubjectRead(SubjectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubjectUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
