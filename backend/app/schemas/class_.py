from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClassBase(BaseModel):
    grade_id: int
    name: str
    is_active: bool = True


class ClassCreate(BaseModel):
    grade_id: int
    name: str


class ClassRead(ClassBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassUpdate(BaseModel):
    grade_id: int | None = None
    name: str | None = None
    is_active: bool | None = None
