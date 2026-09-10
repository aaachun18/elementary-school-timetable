from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScheduleBase(BaseModel):
    schedule_version_id: int
    lesson_id: int
    teacher_id: int | None = None
    time_slot_id: int | None = None
    room_id: int | None = None


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleRead(ScheduleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduleUpdate(BaseModel):
    schedule_version_id: int | None = None
    lesson_id: int | None = None
    teacher_id: int | None = None
    time_slot_id: int | None = None
    room_id: int | None = None
