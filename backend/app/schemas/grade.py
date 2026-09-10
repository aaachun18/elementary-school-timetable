from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GradeBase(BaseModel):
    name: str
    level: int


class GradeCreate(GradeBase):
    pass


class GradeRead(GradeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GradeUpdate(BaseModel):
    name: str | None = None
    level: int | None = None
