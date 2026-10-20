from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.school import School
from app.models.teacher import Teacher
from app.services.grade_levels import (
    GradeBand,
    SlotPosition,
    default_open_slot_ids,
    grade_band,
    last_open_period,
)
from app.services.teacher_periods import (
    NEGATIVE_MAX_MESSAGE,
    NEGATIVE_MIN_MESSAGE,
    RANGE_MESSAGE,
)
from tests.api_helpers import create_enrolled_teacher, create_teacher

# Task 98: one semester's scheduling settings -- the wizard's steps 4-6
# (teachers taking part, their weekly periods range, unavailable slots) and
# step 8 (the slots each grade is open for) -- and the run-scheduler rules
# that come from them.

SEMESTERS = "/api/v1/semesters"


def _messages(response: Any) -> str:
    detail = response.json()["detail"]
    if isinstance(detail, str):
        return detail
    return " ".join(item["msg"] for item in detail)


def _semester(client: TestClient, year: int = 115) -> int:
    year_id = client.post("/api/v1/academic-years/", json={"year": year}).json()["id"]
    response = client.post(f"{SEMESTERS}/", json={"academic_year_id": year_id, "number": 1})
    semester_id: int = response.json()["id"]
    return semester_id


def _slot(client: TestClient, weekday: int, period: int, *, teaching: bool = True) -> int:
    response = client.post(
        "/api/v1/time-slots/",
        json={"weekday": weekday, "period": period, "is_teaching_period": teaching},
    )
    assert response.status_code == 201, response.json()
    slot_id: int = response.json()["id"]
    return slot_id


def _grade(client: TestClient, level: int) -> int:
    response = client.post("/api/v1/grades/", json={"name": f"{level} 年級", "level": level})
    grade_id: int = response.json()["id"]
    return grade_id


def _entry(teacher_id: int, minimum: int = 0, maximum: int = 20, unavailable: list[int] | None = None) -> dict[str, Any]:
    return {
        "teacher_id": teacher_id,
        "min_weekly_periods": minimum,
        "max_weekly_periods": maximum,
        "unavailable_time_slot_ids": unavailable or [],
    }


def _put_teachers(client: TestClient, semester_id: int, entries: list[dict[str, Any]]) -> Any:
    return client.put(f"{SEMESTERS}/{semester_id}/teachers", json={"teachers": entries})


# --- teachers taking part (steps 4-6) ---


def test_teachers_taking_part_are_saved_with_their_settings(client: TestClient) -> None:
    semester_id = _semester(client)
    slot_a, slot_b = _slot(client, 1, 1), _slot(client, 1, 2)
    wang = create_teacher(client, "王老師")
    lin = create_teacher(client, "林老師")

    response = _put_teachers(
        client, semester_id, [_entry(lin, 2, 18, [slot_b, slot_a]), _entry(wang, 0, 10)]
    )

    assert response.status_code == 200, response.json()
    assert response.json() == client.get(f"{SEMESTERS}/{semester_id}/teachers").json()
    assert response.json() == [
        {"teacher_id": wang, "teacher_name": "王老師", "min_weekly_periods": 0,
         "max_weekly_periods": 10, "unavailable_time_slot_ids": []},
        {"teacher_id": lin, "teacher_name": "林老師", "min_weekly_periods": 2,
         "max_weekly_periods": 18, "unavailable_time_slot_ids": sorted([slot_a, slot_b])},
    ]


def test_replacing_drops_teachers_left_out(client: TestClient) -> None:
    semester_id = _semester(client)
    slot = _slot(client, 1, 1)
    wang = create_teacher(client, "王老師")
    lin = create_teacher(client, "林老師")
    _put_teachers(client, semester_id, [_entry(wang, unavailable=[slot]), _entry(lin)])

    response = _put_teachers(client, semester_id, [_entry(lin)])

    assert [item["teacher_id"] for item in response.json()] == [lin]


def test_settings_are_per_semester(client: TestClient) -> None:
    first, second = _semester(client, 115), _semester(client, 116)
    wang = create_teacher(client, "王老師")
    _put_teachers(client, first, [_entry(wang, 1, 5)])

    assert client.get(f"{SEMESTERS}/{second}/teachers").json() == []


@pytest.mark.parametrize(
    ("minimum", "maximum", "message"),
    [
        (20, 15, RANGE_MESSAGE),
        (-1, 10, NEGATIVE_MIN_MESSAGE),
        (0, -1, NEGATIVE_MAX_MESSAGE),
    ],
)
def test_bad_weekly_periods_ranges_are_422(
    client: TestClient, minimum: int, maximum: int, message: str
) -> None:
    """Task 88's rules, now for the semester's own range."""
    semester_id = _semester(client)
    wang = create_teacher(client, "王老師")

    response = _put_teachers(client, semester_id, [_entry(wang, minimum, maximum)])

    assert response.status_code == 422
    assert message in _messages(response)
    assert client.get(f"{SEMESTERS}/{semester_id}/teachers").json() == []


def test_a_teacher_listed_twice_is_422(client: TestClient) -> None:
    semester_id = _semester(client)
    wang = create_teacher(client, "王老師")

    response = _put_teachers(client, semester_id, [_entry(wang), _entry(wang)])

    assert response.status_code == 422
    assert "同一位教師只能出現一次" in _messages(response)


def test_an_inactive_teacher_cannot_take_part(client: TestClient, db_session: Session) -> None:
    semester_id = _semester(client)
    wang = create_teacher(client, "王老師")
    teacher = db_session.get(Teacher, wang)
    assert teacher is not None
    teacher.is_active = False
    db_session.commit()

    response = _put_teachers(client, semester_id, [_entry(wang)])

    assert response.status_code == 409


def test_another_schools_teacher_or_slot_is_422(client: TestClient, db_session: Session) -> None:
    semester_id = _semester(client)
    other_school = School(name="別的學校", is_active=True)
    db_session.add(other_school)
    db_session.flush()
    outsider = Teacher(school_id=other_school.id, name="外校老師", is_active=True,
                       min_weekly_periods=0, max_weekly_periods=0)
    db_session.add(outsider)
    db_session.commit()
    wang = create_teacher(client, "王老師")

    assert _put_teachers(client, semester_id, [_entry(outsider.id)]).status_code == 422
    assert _put_teachers(client, semester_id, [_entry(wang, unavailable=[999999])]).status_code == 422


def test_unknown_semester_is_404(client: TestClient) -> None:
    assert client.get(f"{SEMESTERS}/999999/teachers").status_code == 404
    assert _put_teachers(client, 999999, []).status_code == 404


def test_teacher_account_reads_but_cannot_change(
    client: TestClient, teacher_client: TestClient
) -> None:
    semester_id = _semester(client)

    assert teacher_client.get(f"{SEMESTERS}/{semester_id}/teachers").status_code == 200
    assert _put_teachers(teacher_client, semester_id, []).status_code == 403


# --- grades' open slots (step 8) ---


def test_grade_open_slots_are_saved_and_replaced(client: TestClient) -> None:
    semester_id = _semester(client)
    grade_id = _grade(client, 1)
    slots = [_slot(client, 1, period) for period in (1, 2, 3)]
    url = f"{SEMESTERS}/{semester_id}/grades/{grade_id}/time-slots"

    first = client.put(url, json={"time_slot_ids": [slots[2], slots[0]]})
    second = client.put(url, json={"time_slot_ids": [slots[1]]})

    assert first.json() == {"grade_id": grade_id, "time_slot_ids": sorted([slots[0], slots[2]])}
    assert second.status_code == 200
    assert client.get(f"{SEMESTERS}/{semester_id}/grade-time-slots").json() == [
        {"grade_id": grade_id, "time_slot_ids": [slots[1]]}
    ]


def test_a_grade_needs_at_least_one_open_slot(client: TestClient) -> None:
    semester_id = _semester(client)
    grade_id = _grade(client, 1)

    response = client.put(
        f"{SEMESTERS}/{semester_id}/grades/{grade_id}/time-slots", json={"time_slot_ids": []}
    )

    assert response.status_code == 422
    assert "每個年級至少要開放一個可排節次" in _messages(response)


def test_unknown_grade_or_slot(client: TestClient) -> None:
    semester_id = _semester(client)
    grade_id = _grade(client, 1)

    unknown_grade = client.put(
        f"{SEMESTERS}/{semester_id}/grades/999999/time-slots", json={"time_slot_ids": [1]}
    )
    unknown_slot = client.put(
        f"{SEMESTERS}/{semester_id}/grades/{grade_id}/time-slots", json={"time_slot_ids": [999999]}
    )

    assert unknown_grade.status_code == 404
    assert unknown_slot.status_code == 422


# --- default open slots per band ---


@pytest.mark.parametrize(
    ("level", "band"),
    [(1, GradeBand.LOWER), (2, GradeBand.LOWER), (3, GradeBand.MIDDLE), (4, GradeBand.MIDDLE),
     (5, GradeBand.UPPER), (6, GradeBand.UPPER), (7, GradeBand.JUNIOR_HIGH), (9, GradeBand.JUNIOR_HIGH)],
)
def test_grade_bands(level: int, band: GradeBand) -> None:
    assert grade_band(level) is band


@pytest.mark.parametrize(
    ("band", "last_by_weekday"),
    [
        (GradeBand.LOWER, {1: 5, 2: 8, 3: 5, 4: 5, 5: 5}),
        (GradeBand.MIDDLE, {1: 8, 2: 8, 3: 5, 4: 8, 5: 5}),
        (GradeBand.UPPER, {1: 8, 2: 8, 3: 5, 4: 8, 5: 8}),
        (GradeBand.JUNIOR_HIGH, {1: 8, 2: 8, 3: 8, 4: 8, 5: 8}),
    ],
)
def test_last_open_period_by_band(band: GradeBand, last_by_weekday: dict[int, int]) -> None:
    assert {weekday: last_open_period(band, weekday) for weekday in range(1, 6)} == last_by_weekday


def test_default_open_slots_skip_non_teaching_periods() -> None:
    slots = [
        SlotPosition(time_slot_id=10 + period, weekday=1, period=period, is_teaching_period=period != 4)
        for period in range(0, 9)
    ]

    # 低年級, Monday 0-5, without the lunch break at period 4.
    assert default_open_slot_ids(1, slots) == [10, 11, 12, 13, 15]


def test_default_time_slots_endpoint(client: TestClient) -> None:
    by_position = {
        (weekday, period): _slot(client, weekday, period)
        for weekday in (2, 3)
        for period in range(0, 9)
    }
    lower = _grade(client, 1)
    junior = _grade(client, 8)

    lower_slots = client.get(f"/api/v1/grades/{lower}/default-time-slots").json()
    junior_slots = client.get(f"/api/v1/grades/{junior}/default-time-slots").json()

    # 低年級: Tuesday 0-8, Wednesday 0-5.
    assert lower_slots == [by_position[(2, p)] for p in range(0, 9)] + [
        by_position[(3, p)] for p in range(0, 6)
    ]
    assert junior_slots == [by_position[(w, p)] for w in (2, 3) for p in range(0, 9)]
    assert client.get("/api/v1/grades/999999/default-time-slots").status_code == 404


# --- what run-scheduler does with them ---


def _schedulable(client: TestClient, weekly_periods: int) -> tuple[int, int, int, list[int]]:
    """One 1st-grade class needing `weekly_periods` of one subject, one
    teacher taking part, four Monday slots. Returns (semester_id,
    version_id, grade_id, slot ids)."""
    semester_id = _semester(client)
    grade_id = _grade(client, 1)
    class_id = client.post("/api/v1/classes/", json={"grade_id": grade_id, "name": "一甲"}).json()["id"]
    subject_id = client.post("/api/v1/subjects/", json={"name": "國語"}).json()["id"]
    client.post(
        "/api/v1/class-subject-requirements/",
        json={"semester_id": semester_id, "class_id": class_id, "subject_id": subject_id,
              "weekly_periods": weekly_periods},
    )
    slots = [_slot(client, 1, period) for period in (1, 2, 3, 4)]
    create_enrolled_teacher(client, semester_id, "王老師")
    version_id = client.post(
        "/api/v1/schedule-versions/", json={"semester_id": semester_id, "version_number": 1}
    ).json()["id"]
    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")
    return semester_id, version_id, grade_id, slots


def test_run_scheduler_keeps_a_grade_inside_its_open_slots(client: TestClient) -> None:
    semester_id, version_id, grade_id, slots = _schedulable(client, weekly_periods=2)
    client.put(
        f"{SEMESTERS}/{semester_id}/grades/{grade_id}/time-slots",
        json={"time_slot_ids": [slots[2], slots[3]]},
    )

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 200, response.json()
    placed = {
        row["time_slot_id"]
        for row in client.get("/api/v1/schedules/", params={"schedule_version_id": version_id}).json()
    }
    assert placed == {slots[2], slots[3]}


def test_run_scheduler_reports_too_few_open_slots(client: TestClient) -> None:
    semester_id, version_id, grade_id, slots = _schedulable(client, weekly_periods=3)
    client.put(
        f"{SEMESTERS}/{semester_id}/grades/{grade_id}/time-slots",
        json={"time_slot_ids": [slots[0], slots[1]]},
    )

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    [violation] = response.json()["post_hoc_violations"]
    assert violation["type"] == "STATIC_CLASS_SLOTS_INSUFFICIENT"
    assert violation["message"] == "一甲每週要上 3 堂課，但所屬年級只開放 2 個可排節次"


def test_run_scheduler_without_any_teacher_explains_it(client: TestClient) -> None:
    semester_id, version_id, _, _ = _schedulable(client, weekly_periods=1)
    _put_teachers(client, semester_id, [])

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
    reasons = [r["type"] for f in response.json()["lesson_failures"] for r in f["reasons"]]
    assert reasons == ["NO_CANDIDATE_TEACHER"]


def test_run_scheduler_uses_the_semesters_maximum(client: TestClient) -> None:
    semester_id, version_id, _, _ = _schedulable(client, weekly_periods=2)
    [teacher] = client.get(f"{SEMESTERS}/{semester_id}/teachers").json()
    _put_teachers(client, semester_id, [_entry(teacher["teacher_id"], 0, 1)])

    response = client.post(f"/api/v1/schedule-versions/{version_id}/run-scheduler")

    assert response.status_code == 422
