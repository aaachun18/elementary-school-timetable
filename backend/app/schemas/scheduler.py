from typing import Literal

from pydantic import BaseModel, ConfigDict


class ConstraintViolationDetail(BaseModel):
    """Serializable mirror of scheduling_engine.constraints.base.ConstraintViolation.

    model_config lets this be built directly from the dataclass instance via
    model_validate(violation) -- no manual field-by-field copying needed.
    severity is a plain str here (Severity is itself a str Enum on the
    engine side, so this loses nothing) since Pydantic has no reason to know
    about the engine's own Enum type.
    """

    model_config = ConfigDict(from_attributes=True)

    type: str
    severity: str
    lesson_id: int | None
    teacher_id: int | None
    class_id: int | None
    subject_id: int | None
    time_slot_id: int | None
    message: str
    suggested_action: str | None = None
    room_id: int | None = None
    class_subject_requirement_id: int | None = None


class LessonFailureDetail(BaseModel):
    """Serializable mirror of scheduling_engine.algorithms.resources.LessonFailure."""

    model_config = ConfigDict(from_attributes=True)

    lesson_id: int
    class_subject_requirement_id: int
    reasons: list[ConstraintViolationDetail]


class SchedulerRunResult(BaseModel):
    """200 response: the scheduler placed every Lesson successfully."""

    scheduled_count: int
    backtrack_count: int


class SchedulerFailureDetail(BaseModel):
    """422 response body. failure_type mirrors
    scheduling_engine.algorithms.backtracking.BacktrackingResult.failure_type,
    plus one extra case ("REQUIREMENT_PERIODS_MISMATCH") for when every
    Lesson placed fine but the finished schedule still fails the post-hoc H7
    check -- that case leaves BacktrackingResult.failure_type as None (it
    isn't a search-level outcome), so it needs its own label here to avoid
    reporting a misleading null failure_type to the API caller.
    """

    failure_type: Literal[
        "DEFINITELY_INFEASIBLE",
        "SEARCH_LIMIT_EXCEEDED",
        "TIMEOUT",
        "REQUIREMENT_PERIODS_MISMATCH",
    ]
    lesson_failures: list[LessonFailureDetail]
    post_hoc_violations: list[ConstraintViolationDetail]
    backtrack_count: int
