from datetime import datetime

from pydantic import BaseModel, ConfigDict

# Task 98: a teacher is created (and 停用 / 啟用) together with its 一般老師
# account (app/services/user.py); its weekly periods range and unavailable
# slots are set per semester (app/schemas/semester_settings.py), and there
# are no teaching qualifications any more. What is left here is reading
# the school's teachers and renaming one.


class TeacherRead(BaseModel):
    id: int
    name: str
    is_active: bool
    # The teacher's 一般老師 account, if it has one.
    user_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeacherUpdate(BaseModel):
    name: str | None = None
