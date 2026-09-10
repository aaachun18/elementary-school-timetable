from datetime import datetime, time

from pydantic import BaseModel, ConfigDict


class TimeSlotBase(BaseModel):
    weekday: int
    period: int
    start_time: time | None = None
    end_time: time | None = None
    is_teaching_period: bool = True


class TimeSlotCreate(TimeSlotBase):
    pass


class TimeSlotRead(TimeSlotBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimeSlotUpdate(BaseModel):
    weekday: int | None = None
    period: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    is_teaching_period: bool | None = None
