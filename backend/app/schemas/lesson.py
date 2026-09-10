from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LessonRead(BaseModel):
    id: int
    class_subject_requirement_id: int
    sequence_number: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
