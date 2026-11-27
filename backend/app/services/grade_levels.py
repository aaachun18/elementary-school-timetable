"""Task 98: the bands of grade levels -- 國小 低/中/高年級, 國中, 高中 --
and the default time slots each band is open for (wizard step 8). Plain
functions, no FastAPI, no database: services/semester_settings.py applies
default_open_slot_ids() to a school's time slots. Which levels a school
has comes from its type (app/services/school_structure.py)."""

from dataclasses import dataclass
from enum import Enum

from app.models.grade_class import MAX_GRADE_LEVEL, MIN_GRADE_LEVEL

LEVEL_MESSAGE = (
    f"年級必須介於 {MIN_GRADE_LEVEL} 到 {MAX_GRADE_LEVEL}（國小 1–6、國中 7–9、高中 10–12）"
)


def check_grade_level(level: int | None) -> int | None:
    if level is not None and not MIN_GRADE_LEVEL <= level <= MAX_GRADE_LEVEL:
        raise ValueError(LEVEL_MESSAGE)
    return level


class GradeBand(str, Enum):
    LOWER = "LOWER"  # 低年級 1-2
    MIDDLE = "MIDDLE"  # 中年級 3-4
    UPPER = "UPPER"  # 高年級 5-6
    JUNIOR_HIGH = "JUNIOR_HIGH"  # 國中 7-9
    SENIOR_HIGH = "SENIOR_HIGH"  # 高中 10-12


def grade_band(level: int) -> GradeBand:
    check_grade_level(level)
    if level <= 2:
        return GradeBand.LOWER
    if level <= 4:
        return GradeBand.MIDDLE
    if level <= 6:
        return GradeBand.UPPER
    if level <= 9:
        return GradeBand.JUNIOR_HIGH
    return GradeBand.SENIOR_HIGH


# Weekdays: 1 = Monday ... 5 = Friday (TimeSlot.weekday). Periods are the
# database's: 0 早自習, 1-4 the morning, 5 午休, then the afternoon up to
# 放學 (國小 9, 國中 / 高中 10). People count only teaching periods, so the
# afternoon's 6-8 are 「第 5-7 節」 on screen.
FIRST_OPEN_PERIOD = 1
SHORT_DAY_LAST_PERIOD = 4  # morning only: 第 1-4 節
FULL_DAY_LAST_PERIOD = 8  # 國小 whole day: 第 1-7 節
SECONDARY_LAST_PERIOD = 9  # 國中 / 高中 whole day: 第 1-8 節
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
    """The last (database) period a band is open for by default on a
    weekday, as people count it:
    - 一、二年級: Tuesday 第 1-7 節, every other day 第 1-4 節;
    - 三、四年級: Wednesday and Friday 第 1-4 節, every other day 第 1-7 節;
    - 五、六年級: Wednesday 第 1-4 節, every other day 第 1-7 節;
    - 國中 / 高中: every day 第 1-8 節."""
    if band is GradeBand.LOWER:
        return FULL_DAY_LAST_PERIOD if weekday == TUESDAY else SHORT_DAY_LAST_PERIOD
    if band is GradeBand.MIDDLE:
        return SHORT_DAY_LAST_PERIOD if weekday in (WEDNESDAY, FRIDAY) else FULL_DAY_LAST_PERIOD
    if band is GradeBand.UPPER:
        return SHORT_DAY_LAST_PERIOD if weekday == WEDNESDAY else FULL_DAY_LAST_PERIOD
    return SECONDARY_LAST_PERIOD


def default_open_slot_ids(level: int, slots: list[SlotPosition]) -> list[int]:
    """The school time slots a grade of this level is open for by default:
    schedulable periods only (早自習, 午休, 放學 or whatever the school marked
    not schedulable is never open), within the band's period range for the
    slot's weekday. In the order of `slots`."""
    band = grade_band(level)
    return [
        slot.time_slot_id
        for slot in slots
        if slot.is_teaching_period
        and FIRST_OPEN_PERIOD <= slot.period <= last_open_period(band, slot.weekday)
    ]
