from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RoomBase(BaseModel):
    name: str
    room_type: str
    capacity: int
    is_active: bool = True


class RoomCreate(BaseModel):
    name: str
    room_type: str
    capacity: int


class RoomRead(RoomBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoomUpdate(BaseModel):
    name: str | None = None
    room_type: str | None = None
    capacity: int | None = None
    is_active: bool | None = None
