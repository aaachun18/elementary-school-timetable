from pydantic import BaseModel, ConfigDict


class DeactivationImpactRead(BaseModel):
    """GET .../deactivation-impact: what 停用 would touch (counts only; see
    app/services/deactivation.py for what each one counts)."""

    published_records: int
    other_records: int
    not_scheduled_records: int
    grade_requirements: int

    model_config = ConfigDict(from_attributes=True)
