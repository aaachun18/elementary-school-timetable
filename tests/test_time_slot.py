from fastapi.testclient import TestClient
from tests.api_helpers import create_teacher, enroll_teacher
from tests.conftest import next_free_grade_level_via_api


def _time_slot_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "weekday": 1,
        "period": 1,
        "start_time": "08:00:00",
        "end_time": "08:40:00",
        "is_teaching_period": True,
    }
    payload.update(overrides)
    return payload


def test_create_time_slot(client: TestClient) -> None:
    response = client.post("/api/v1/time-slots/", json=_time_slot_payload())

    assert response.status_code == 201
    data = response.json()
    assert data["weekday"] == 1
    assert data["period"] == 1
    assert data["start_time"] == "08:00:00"
    assert data["end_time"] == "08:40:00"
    assert data["is_teaching_period"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_time_slot_without_start_end_time(client: TestClient) -> None:
    response = client.post(
        "/api/v1/time-slots/",
        json={"weekday": 1, "period": 1, "is_teaching_period": True},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["start_time"] is None
    assert data["end_time"] is None


def test_create_time_slot_can_set_is_teaching_period(client: TestClient) -> None:
    # Unlike is_active elsewhere, is_teaching_period is a structural
    # attribute decided at creation time (Task 9 design decision), so
    # TimeSlotCreate is expected to honor it rather than force it to True.
    response = client.post(
        "/api/v1/time-slots/", json=_time_slot_payload(is_teaching_period=False)
    )

    assert response.status_code == 201
    assert response.json()["is_teaching_period"] is False


def test_get_time_slot_list(client: TestClient) -> None:
    client.post("/api/v1/time-slots/", json=_time_slot_payload(period=2))

    response = client.get("/api/v1/time-slots/")

    assert response.status_code == 200
    periods = [item["period"] for item in response.json()]
    assert 2 in periods


def test_get_time_slot_by_id(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/time-slots/", json=_time_slot_payload(period=3)
    )
    time_slot_id = create_response.json()["id"]

    response = client.get(f"/api/v1/time-slots/{time_slot_id}")

    assert response.status_code == 200
    assert response.json()["period"] == 3


def test_get_time_slot_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/time-slots/999999")

    assert response.status_code == 404


def test_update_time_slot(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/time-slots/", json=_time_slot_payload(period=4)
    )
    time_slot_id = create_response.json()["id"]

    response = client.patch(f"/api/v1/time-slots/{time_slot_id}", json={"period": 5})

    assert response.status_code == 200
    assert response.json()["period"] == 5


def test_update_time_slot_not_found(client: TestClient) -> None:
    response = client.patch("/api/v1/time-slots/999999", json={"period": 1})

    assert response.status_code == 404


def test_delete_time_slot(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/time-slots/", json=_time_slot_payload(period=6)
    )
    time_slot_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/time-slots/{time_slot_id}")

    assert response.status_code == 204


def test_delete_time_slot_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/time-slots/999999")

    assert response.status_code == 404


def test_create_time_slot_weekday_check_violation(client: TestClient) -> None:
    response = client.post("/api/v1/time-slots/", json=_time_slot_payload(weekday=9))

    assert response.status_code == 409


# --- label (Task 35) ---


def test_create_time_slot_with_label(client: TestClient) -> None:
    response = client.post(
        "/api/v1/time-slots/",
        json=_time_slot_payload(
            period=0, is_teaching_period=False, label="早自習"
        ),
    )

    assert response.status_code == 201
    assert response.json()["label"] == "早自習"


def test_create_time_slot_without_label_defaults_to_null(client: TestClient) -> None:
    response = client.post("/api/v1/time-slots/", json=_time_slot_payload(period=7))

    assert response.status_code == 201
    assert response.json()["label"] is None


def test_update_time_slot_label(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/time-slots/", json=_time_slot_payload(period=8)
    )
    time_slot_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/time-slots/{time_slot_id}", json={"label": "午餐/午休"}
    )

    assert response.status_code == 200
    assert response.json()["label"] == "午餐/午休"


# --- Task 50 / 98: deleting a TimeSlot also clears the rows that only
# describe it -- a teacher's unavailable slot and a grade's open slot in a
# semester (owned settings, no meaning once the slot is gone) -- but is
# still blocked by a REAL reference: Lesson.fixed_time_slot_id or
# Schedule.time_slot_id. When blocked, no setting is touched. ---


def _settings_on_slot(client: TestClient, time_slot_id: int, year: int) -> tuple[int, int, int]:
    """A semester where one teacher is unavailable at the slot and one grade
    is open at it. Returns (semester_id, teacher_id, grade_id)."""
    academic_year_id = client.post(
        "/api/v1/academic-years/", json={"year": year}
    ).json()["id"]
    semester_id = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 1},
    ).json()["id"]
    teacher_id = create_teacher(client, f"Unavailable Teacher {year}")
    enroll_teacher(client, semester_id, teacher_id, unavailable_time_slot_ids=[time_slot_id])
    grade_id = client.post(
        "/api/v1/grades/", json={"name": f"Open Grade {year}", "level": next_free_grade_level_via_api(client)}
    ).json()["id"]
    response = client.put(
        f"/api/v1/semesters/{semester_id}/grades/{grade_id}/time-slots",
        json={"time_slot_ids": [time_slot_id]},
    )
    assert response.status_code == 200
    return semester_id, teacher_id, grade_id


def _unavailable(client: TestClient, semester_id: int) -> list[int]:
    [teacher] = client.get(f"/api/v1/semesters/{semester_id}/teachers").json()
    slot_ids: list[int] = teacher["unavailable_time_slot_ids"]
    return slot_ids


def _open_slots(client: TestClient, semester_id: int) -> list[list[int]]:
    return [
        item["time_slot_ids"]
        for item in client.get(f"/api/v1/semesters/{semester_id}/grade-time-slots").json()
    ]


def _create_lesson(client: TestClient, year: int) -> tuple[int, int]:
    """Returns (lesson_id, schedule_version_id) for a freshly-synced,
    single-Lesson requirement -- same shape as test_schedule.py's own
    helper."""
    academic_year_id = client.post(
        "/api/v1/academic-years/", json={"year": year}
    ).json()["id"]
    semester_id = client.post(
        "/api/v1/semesters/",
        json={"academic_year_id": academic_year_id, "number": 1},
    ).json()["id"]
    grade_id = client.post(
        "/api/v1/grades/", json={"name": f"Grade {year}", "level": next_free_grade_level_via_api(client)}
    ).json()["id"]
    class_id = client.post(
        "/api/v1/classes/", json={"grade_id": grade_id, "name": f"Class {year}"}
    ).json()["id"]
    subject_id = client.post(
        "/api/v1/subjects/", json={"name": f"Subject {year}"}
    ).json()["id"]
    client.post(
        "/api/v1/class-subject-requirements/",
        json={
            "semester_id": semester_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "weekly_periods": 1,
        },
    )
    version_id = client.post(
        "/api/v1/schedule-versions/",
        json={"semester_id": semester_id, "version_number": 1, "status": "DRAFT"},
    ).json()["id"]
    generate_response = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    )
    lesson_id: int = generate_response.json()["created_lessons"][0]["lesson_id"]
    return lesson_id, version_id


def test_delete_time_slot_clears_the_semester_settings_on_it(
    client: TestClient,
) -> None:
    time_slot_id = client.post(
        "/api/v1/time-slots/", json=_time_slot_payload(period=9)
    ).json()["id"]
    semester_id, teacher_id, _ = _settings_on_slot(client, time_slot_id, year=2109)

    response = client.delete(f"/api/v1/time-slots/{time_slot_id}")

    assert response.status_code == 204
    # The setting rows are genuinely gone, not just the slot; the teacher
    # still takes part in the semester.
    assert _unavailable(client, semester_id) == []
    assert _open_slots(client, semester_id) == []
    assert client.get(f"/api/v1/teachers/{teacher_id}").status_code == 200


def test_delete_time_slot_blocked_by_fixed_lesson_keeps_settings(
    client: TestClient,
) -> None:
    time_slot_id = client.post(
        "/api/v1/time-slots/", json=_time_slot_payload(period=10)
    ).json()["id"]
    semester_id, _, _ = _settings_on_slot(client, time_slot_id, year=2112)
    lesson_id, _ = _create_lesson(client, year=2110)
    fix_response = client.patch(
        f"/api/v1/lessons/{lesson_id}/fix-time-slot",
        json={"time_slot_id": time_slot_id},
    )
    assert fix_response.status_code == 200

    response = client.delete(f"/api/v1/time-slots/{time_slot_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "此資料仍被其他資料參照，無法刪除"
    # TimeSlot AND the settings on it all survived -- the transaction was
    # fully rolled back, not partially applied.
    assert client.get(f"/api/v1/time-slots/{time_slot_id}").status_code == 200
    assert _unavailable(client, semester_id) == [time_slot_id]
    assert _open_slots(client, semester_id) == [[time_slot_id]]
    assert client.get(f"/api/v1/lessons/{lesson_id}").json()["fixed_time_slot_id"] == (
        time_slot_id
    )


def test_delete_time_slot_blocked_by_schedule_keeps_settings(
    client: TestClient,
) -> None:
    time_slot_id = client.post(
        "/api/v1/time-slots/", json=_time_slot_payload(period=11)
    ).json()["id"]
    semester_id, _, _ = _settings_on_slot(client, time_slot_id, year=2113)
    lesson_id, version_id = _create_lesson(client, year=2111)
    create_schedule_response = client.post(
        "/api/v1/schedules/",
        json={
            "schedule_version_id": version_id,
            "lesson_id": lesson_id,
            "time_slot_id": time_slot_id,
        },
    )
    assert create_schedule_response.status_code == 201

    response = client.delete(f"/api/v1/time-slots/{time_slot_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "此資料仍被其他資料參照，無法刪除"
    assert client.get(f"/api/v1/time-slots/{time_slot_id}").status_code == 200
    assert _unavailable(client, semester_id) == [time_slot_id]
