"""Task 88: the rules for a teacher's weekly periods range, in one place:
the request schemas (app/schemas/teacher.py) check a single value or a
complete create body, the update service checks the values a PATCH would
leave behind. Plain functions, no FastAPI -- the messages reach the user as
the 422 detail."""

NEGATIVE_MIN_MESSAGE = "最低每週節數不得為負數"
NEGATIVE_MAX_MESSAGE = "最高每週節數不得為負數"
RANGE_MESSAGE = "最低每週節數不得大於最高每週節數"


def check_not_negative(value: int | None, message: str) -> int | None:
    if value is not None and value < 0:
        raise ValueError(message)
    return value


def check_periods_range(min_weekly_periods: int, max_weekly_periods: int) -> None:
    if min_weekly_periods > max_weekly_periods:
        raise ValueError(RANGE_MESSAGE)
