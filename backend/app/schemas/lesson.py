from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LessonRead(BaseModel):
    id: int
    class_subject_requirement_id: int
    sequence_number: int
    fixed_time_slot_id: int | None
    # Task 87: the lesson's block in its requirement's lesson_pattern
    # (block_no 1 = first/longest block; block_seq 1 = first period of
    # it). Both null when the requirement has no pattern.
    block_no: int | None
    block_seq: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonFixTimeSlot(BaseModel):
    """Body for PATCH /lessons/{id}/fix-time-slot. time_slot_id is required
    (not defaulted) so the caller must explicitly say null to clear a fixed
    slot, rather than omitting the field by accident."""

    time_slot_id: int | None
