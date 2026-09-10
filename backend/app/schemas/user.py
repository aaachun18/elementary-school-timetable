from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    username: str
    role: Literal["ADMIN", "TEACHER"]


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
