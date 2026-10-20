"""Task 98: the rules for a grade's level -- 國小 1-6, 國中 7-9 -- and the
default time slots each band of grades is open for (wizard step 8). Plain
functions, no FastAPI, no database: the request schemas turn
check_grade_level()'s ValueError into a 422 with its Chinese message
(before the database CHECK ck_grades_level_valid would 409), and
services/semester_settings.py applies default_open_slot_ids() to a
school's time slots."""

from dataclasses import dataclass
from enum import Enum

from app.models.grade_class import MAX_GRADE_LEVEL, MIN_GRADE_LEVEL

LEVEL_MESSAGE = f"年級必須介於 {MIN_GRADE_LEVEL} 到 {MAX_GRADE_LEVEL}（國小 1–6、國中 7–9）"


def check_grade_level(level: int | None) -> int | None:
    if level is not None and not MIN_GRADE_LEVEL <= level <= MAX_GRADE_LEVEL:
        raise ValueError(LEVEL_MESSAGE)
    return level


class GradeBand(str, Enum):
    LOWER = "LOWER"  # 低年級 1-2
    MIDDLE = "MIDDLE"  # 中年級 3-4
    UPPER = "UPPER"  # 高年級 5-6
    JUNIOR_HIGH = "JUNIOR_HIGH"  # 國中 7-9


def grade_band(level: int) -> GradeBand:
    check_grade_level(level)
    if level <= 2:
        return GradeBand.LOWER
    if level <= 4:
        return GradeBand.MIDDLE
    if level <= 6:
        return GradeBand.UPPER
    return GradeBand.JUNIOR_HIGH


# Weekdays: 1 = Monday ... 5 = Friday (TimeSlot.weekday). Periods count
# from 0 (早自習 / 第 0 節) to 8.
FIRST_PERIOD = 0
SHORT_DAY_LAST_PERIOD = 5  # "0-5 節"
FULL_DAY_LAST_PERIOD = 8  # "0-8 節"
TUESDAY = 2
WEDNESDAY = 3
FRIDAY = 5


@dataclass(frozen=True)
class SlotPosition:
    time_slot_id: int
    weekday: int
    period: int
    is_teaching_period: bool


def last_open_period(band: GradeBand, weekday: int) -> int:
    """The last period a band is open for by default on a weekday:
    - 低年級: Tuesday 0-8, every other day 0-5;
    - 中年級: Wednesday and Friday 0-5, every other day 0-8;
    - 高年級: Wednesday 0-5, every other day 0-8;
    - 國中: every day 0-8."""
    if band is GradeBand.LOWER:
        return FULL_DAY_LAST_PERIOD if weekday == TUESDAY else SHORT_DAY_LAST_PERIOD
    if band is GradeBand.MIDDLE:
        return SHORT_DAY_LAST_PERIOD if weekday in (WEDNESDAY, FRIDAY) else FULL_DAY_LAST_PERIOD
    if band is GradeBand.UPPER:
        return SHORT_DAY_LAST_PERIOD if weekday == WEDNESDAY else FULL_DAY_LAST_PERIOD
    return FULL_DAY_LAST_PERIOD


def default_open_slot_ids(level: int, slots: list[SlotPosition]) -> list[int]:
    """The school time slots a grade of this level is open for by default:
    teaching periods only (a lunch break is never open), within the band's
    period range for the slot's weekday. In the order of `slots`."""
    band = grade_band(level)
    return [
        slot.time_slot_id
        for slot in slots
        if slot.is_teaching_period
        and FIRST_PERIOD <= slot.period <= last_open_period(band, slot.weekday)
    ]
