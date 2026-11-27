"""Task 98: the rule for a requirement's weekly periods -- 1 to 6 a week
(the wizard's 節數 1–6). Plain functions, no FastAPI; the request schemas
(app/schemas/class_subject_requirement.py) turn the ValueError into a 422
with this Chinese message."""

MIN_WEEKLY_PERIODS = 1
MAX_WEEKLY_PERIODS = 6

WEEKLY_PERIODS_MESSAGE = (
    f"每週節數必須介於 {MIN_WEEKLY_PERIODS} 到 {MAX_WEEKLY_PERIODS}"
)


def check_weekly_periods(value: int | None) -> int | None:
    if value is not None and not MIN_WEEKLY_PERIODS <= value <= MAX_WEEKLY_PERIODS:
        raise ValueError(WEEKLY_PERIODS_MESSAGE)
    return value
