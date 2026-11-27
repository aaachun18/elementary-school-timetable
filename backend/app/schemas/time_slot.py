from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TimeSlotRead(BaseModel):
    id: int
    weekday: int
    period: int
    is_teaching_period: bool
    label: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# A school's grid is fixed (built with the school): only whether a slot is
# schedulable and its label can change.
class TimeSlotUpdate(BaseModel):
    is_teaching_period: bool | None = None
    label: str | None = None


class TimeSlotBulkUpdateItem(TimeSlotUpdate):
    id: int


class TimeSlotBulkUpdate(BaseModel):
    """PATCH /time-slots/: the 學校資料 timetable's 儲存 -- every changed
    cell at once, applied all or nothing."""

    time_slots: list[TimeSlotBulkUpdateItem]
