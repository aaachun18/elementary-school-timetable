from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.services.requirement_rules import check_weekly_periods


def _weekly_periods(value: int) -> int:
    # 1-6 periods a week (ValueError -> 422, Chinese message).
    check_weekly_periods(value)
    return value


class GradeSubjectRequirementCreate(BaseModel):
    grade_id: int
    subject_id: int
    weekly_periods: int

    _check_weekly_periods = field_validator("weekly_periods")(_weekly_periods)


class GradeSubjectRequirementRead(BaseModel):
    id: int
    grade_id: int
    subject_id: int
    weekly_periods: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Only the number of periods changes; another grade or subject is a new row.
class GradeSubjectRequirementUpdate(BaseModel):
    weekly_periods: int

    _check_weekly_periods = field_validator("weekly_periods")(_weekly_periods)
