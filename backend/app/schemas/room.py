from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# How many classes may use a room at the same time.
MIN_MAX_CLASSES = 1
MAX_MAX_CLASSES = 10


# Task 98: a 教學組長 only keeps a room's name; rooms have no type any more
# -- a requirement names the one room it needs
# (ClassSubjectRequirement.required_room_id). Room.room_type stays in the
# database, unused.
class RoomBase(BaseModel):
    name: str
    is_active: bool = True
    max_classes: int = 1


class RoomCreate(BaseModel):
    name: str
    max_classes: int = Field(default=1, ge=MIN_MAX_CLASSES, le=MAX_MAX_CLASSES)


class RoomRead(RoomBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoomUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    max_classes: int | None = Field(default=None, ge=MIN_MAX_CLASSES, le=MAX_MAX_CLASSES)
