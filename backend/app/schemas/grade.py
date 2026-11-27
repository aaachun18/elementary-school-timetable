from datetime import datetime

from pydantic import BaseModel, ConfigDict


# Read only: a school's grades are built with the school from its type
# (app/services/school_structure.py) and never created, changed or deleted
# through the API.
class GradeRead(BaseModel):
    id: int
    name: str
    level: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
