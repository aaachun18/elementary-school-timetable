"""The fixed structure a school gets from its type
(app/services/school_structure.py): plain functions, no database."""

import pytest

from app.services.school_structure import (
    ClassNameStyle,
    SchoolType,
    chinese_number,
    class_name_options,
    default_time_slots,
    grade_name,
)


@pytest.mark.parametrize(
    ("value", "text"),
    [(1, "一"), (9, "九"), (10, "十"), (11, "十一"), (19, "十九"), (20, "二十"), (21, "二十一"), (30, "三十")],
)
def test_chinese_number(value: int, text: str) -> None:
    assert chinese_number(value) == text


def test_chinese_number_outside_1_to_99_is_refused() -> None:
    with pytest.raises(ValueError):
        chinese_number(0)


def test_grade_names_show_senior_high_as_one_to_three() -> None:
    assert [grade_name(level) for level in (1, 6, 7, 9, 10, 12)] == [
        "一年級", "六年級", "七年級", "九年級", "一年級", "三年級"
    ]


@pytest.mark.parametrize(
    ("school_type", "last_period"),
    [(SchoolType.ELEMENTARY, 9), (SchoolType.JUNIOR_HIGH, 10), (SchoolType.SENIOR_HIGH, 10)],
)
def test_default_time_slots(school_type: SchoolType, last_period: int) -> None:
    slots = default_time_slots(school_type)

    assert len(slots) == 5 * (last_period + 1)
    assert {(slot.weekday, slot.period) for slot in slots} == {
        (weekday, period) for weekday in range(1, 6) for period in range(0, last_period + 1)
    }
    closed = {(slot.period, slot.label) for slot in slots if not slot.is_teaching_period}
    assert closed == {(0, "早自習"), (5, "午休"), (last_period, "放學")}
    assert all(slot.label is None for slot in slots if slot.is_teaching_period)


def test_class_name_options_per_style() -> None:
    numbers = class_name_options(1, ClassNameStyle.NUMBER)
    stems = class_name_options(1, ClassNameStyle.HEAVENLY_STEM)
    virtues = class_name_options(1, ClassNameStyle.VIRTUE)

    assert (len(numbers), numbers[0], numbers[10], numbers[-1]) == (30, "一年一班", "一年十一班", "一年三十班")
    assert (len(stems), stems[0], stems[-1]) == (10, "一年甲班", "一年癸班")
    assert virtues == [f"一年{token}班" for token in "忠孝仁愛信義和平"]


def test_class_name_options_use_the_displayed_year() -> None:
    assert class_name_options(8, ClassNameStyle.HEAVENLY_STEM)[0] == "八年甲班"
    assert class_name_options(11, ClassNameStyle.HEAVENLY_STEM)[0] == "二年甲班"
