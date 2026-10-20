from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.services.school_structure import ClassNameStyle


class ClassBase(BaseModel):
    grade_id: int
    name_style: ClassNameStyle
    name: str


# A class is only created and deleted, never edited: its name is one of
# class_name_options(grade, name_style) (checked by services/class_.py).
class ClassCreate(ClassBase):
    pass


class ClassRead(ClassBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
