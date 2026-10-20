"""The fixed structure a school gets from its type (國小 / 國中 / 高中):
which grades it has, its weekly time slot grid, and the class names its
classes may use. Plain functions, no FastAPI, no database:
services/school.py builds a new school's grades and time slots from
these, services/class_.py checks a class name against them.

Grade levels are stored school-type-wide unique -- 國小 1-6, 國中 7-9,
高中 10-12 -- so a level alone says which stage it is; 高中 10-12 are
shown as 一到三年級.
"""

from dataclasses import dataclass
from enum import Enum


class SchoolType(str, Enum):
    ELEMENTARY = "ELEMENTARY"  # 國小
    JUNIOR_HIGH = "JUNIOR_HIGH"  # 國中
    SENIOR_HIGH = "SENIOR_HIGH"  # 高中


GRADE_LEVELS: dict[SchoolType, tuple[int, ...]] = {
    SchoolType.ELEMENTARY: (1, 2, 3, 4, 5, 6),
    SchoolType.JUNIOR_HIGH: (7, 8, 9),
    SchoolType.SENIOR_HIGH: (10, 11, 12),
}

# 高中 10-12 are 高中一到三年級.
SENIOR_HIGH_FIRST_LEVEL = 10

CHINESE_NUMERALS = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十")


def chinese_number(value: int) -> str:
    """1 -> 一, 10 -> 十, 12 -> 十二, 20 -> 二十, 30 -> 三十 (1-99)."""
    if not 1 <= value <= 99:
        raise ValueError(f"{value} is outside 1-99")
    tens, ones = divmod(value, 10)
    if tens == 0:
        return CHINESE_NUMERALS[ones - 1]
    tens_text = "" if tens == 1 else CHINESE_NUMERALS[tens - 1]
    ones_text = "" if ones == 0 else CHINESE_NUMERALS[ones - 1]
    return f"{tens_text}十{ones_text}"


def displayed_year(level: int) -> int:
    """The year shown to people: 高中 10-12 -> 1-3, every other level as is."""
    return level - SENIOR_HIGH_FIRST_LEVEL + 1 if level >= SENIOR_HIGH_FIRST_LEVEL else level


def grade_name(level: int) -> str:
    """1 -> 一年級, 7 -> 七年級, 10 -> 一年級 (高中)."""
    return f"{chinese_number(displayed_year(level))}年級"


# --- Time slots ---

WEEKDAYS = (1, 2, 3, 4, 5)  # Monday ... Friday (TimeSlot.weekday)
FIRST_PERIOD = 0
LUNCH_PERIOD = 5
LAST_PERIOD: dict[SchoolType, int] = {
    SchoolType.ELEMENTARY: 9,
    SchoolType.JUNIOR_HIGH: 10,
    SchoolType.SENIOR_HIGH: 10,
}
MORNING_LABEL = "早自習"
LUNCH_LABEL = "午休"
DISMISSAL_LABEL = "放學"


@dataclass(frozen=True)
class DefaultTimeSlot:
    weekday: int
    period: int
    is_teaching_period: bool
    label: str | None


def default_time_slots(school_type: SchoolType) -> list[DefaultTimeSlot]:
    """A new school's whole week: Monday-Friday, periods 0 to the last
    one (國小 9, 國中/高中 10). Period 0 (早自習), 5 (午休) and the last
    (放學) are not schedulable; every other period is, with no label."""
    last_period = LAST_PERIOD[school_type]
    fixed_labels = {
        FIRST_PERIOD: MORNING_LABEL,
        LUNCH_PERIOD: LUNCH_LABEL,
        last_period: DISMISSAL_LABEL,
    }
    return [
        DefaultTimeSlot(
            weekday=weekday,
            period=period,
            is_teaching_period=period not in fixed_labels,
            label=fixed_labels.get(period),
        )
        for weekday in WEEKDAYS
        for period in range(FIRST_PERIOD, last_period + 1)
    ]


# --- Class names ---


class ClassNameStyle(str, Enum):
    NUMBER = "NUMBER"  # 一二三 … 三十
    HEAVENLY_STEM = "HEAVENLY_STEM"  # 甲乙丙 … 癸
    VIRTUE = "VIRTUE"  # 忠孝仁愛信義和平


CLASS_NUMBER_COUNT = 30
HEAVENLY_STEMS = ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸")
VIRTUES = ("忠", "孝", "仁", "愛", "信", "義", "和", "平")


def class_name_tokens(style: ClassNameStyle) -> tuple[str, ...]:
    if style is ClassNameStyle.NUMBER:
        return tuple(chinese_number(number) for number in range(1, CLASS_NUMBER_COUNT + 1))
    if style is ClassNameStyle.HEAVENLY_STEM:
        return HEAVENLY_STEMS
    return VIRTUES


def class_name_options(level: int, style: ClassNameStyle) -> list[str]:
    """Every name a class of this grade may take in this style, expanded
    from the grade: 一年級 + 甲乙丙 -> 一年甲班, 一年乙班 ..."""
    prefix = f"{chinese_number(displayed_year(level))}年"
    return [f"{prefix}{token}班" for token in class_name_tokens(style)]
