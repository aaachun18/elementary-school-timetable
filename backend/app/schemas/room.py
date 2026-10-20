from datetime import datetime

from pydantic import BaseModel, ConfigDict


# Task 98: a 教學組長 only keeps a room's name (and capacity); rooms have no
# type any more -- a requirement names the one room it needs
# (ClassSubjectRequirement.required_room_id). Room.room_type stays in the
# database, unused.
class RoomBase(BaseModel):
    name: str
    capacity: int | None = None
    is_active: bool = True


class RoomCreate(BaseModel):
    name: str
    capacity: int | None = None


class RoomRead(RoomBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoomUpdate(BaseModel):
    name: str | None = None
    capacity: int | None = None
    is_active: bool | None = None
