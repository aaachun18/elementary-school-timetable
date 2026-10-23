from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.services.school_structure import ClassNameStyle


class ClassBase(BaseModel):
    grade_id: int
    name_style: ClassNameStyle
    name: str


# A class is only created and deleted, never edited: its name is one of
# class_name_options(grade, name_style) (checked by services/class_.py).
class ClassCreate(ClassBase):
    pass


class ClassBatchCreate(BaseModel):
    """批次新增: `count` more classes of the grade in this name style -- the
    style's first names the grade doesn't use yet (一年甲班 and 一年乙班
    exist -> 一年丙班, 一年丁班 ...)."""

    grade_id: int
    name_style: ClassNameStyle
    count: int = Field(ge=1)


class ClassRead(ClassBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
