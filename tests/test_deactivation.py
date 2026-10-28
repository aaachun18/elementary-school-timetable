"""停用: classes (停用 / 啟用, 409 CLASS_IN_USE instead of a delete), the
停用影響 counts of teachers / subjects / rooms / classes, new scheduling
leaving 停用 classes and subjects out (sync), the hidden 年級科目需求 of a
停用 subject, and the read-only 排課前檢查 (preflight)."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.models.lesson import Lesson
from app.models.schedule import Schedule
from tests.api_helpers import (
    create_class,
    create_grade,
    create_record,
    create_teacher,
    db_of,
    mark_status,
)

CLASSES = "/api/v1/classes"
CSR = "/api/v1/class-subject-requirements"
RULES = "/api/v1/grade-subject-requirements"
VERSIONS = "/api/v1/schedule-versions"


def _semester(client: TestClient, year: int = 115) -> int:
    year_id = client.post("/api/v1/academic-years/", json={"year": year}).json()["id"]
    semester_id: int = client.post(
        "/api/v1/semesters/", json={"academic_year_id": year_id, "number": 1}
    ).json()["id"]
    return semester_id


def _subject(client: TestClient, name: str) -> int:
    response = client.post("/api/v1/subjects/", json={"name": name})
    assert response.status_code == 201, response.json()
    subject_id: int = response.json()["id"]
    return subject_id


def _rule(client: TestClient, grade_id: int, subject_id: int, weekly_periods: int) -> None:
    response = client.post(
        f"{RULES}/",
        json={"grade_id": grade_id, "subject_id": subject_id, "weekly_periods": weekly_periods},
    )
    assert response.status_code == 201, response.json()


def _sync(client: TestClient, record_id: int) -> dict:
    response = client.post(f"{CSR}/sync", json={"schedule_version_id": record_id})
    assert response.status_code == 200, response.json()
    data: dict = response.json()
    return data


def _requirement_keys(client: TestClient, record_id: int) -> set[tuple[int, int]]:
    rows = client.get(f"{CSR}/", params={"schedule_version_id": record_id, "limit": 1000}).json()
    return {(row["class_id"], row["subject_id"]) for row in rows}


def _school(client: TestClient) -> tuple[int, int, int, int]:
    """One grade with two classes and one subject rule (2 periods)."""
    grade_id = create_grade(client, "一年級", level=1)
    first = create_class(client, grade_id, "一年甲班")
    second = create_class(client, grade_id, "一年乙班")
    subject_id = _subject(client, "國語文")
    _rule(client, grade_id, subject_id, 2)
    return grade_id, first, second, subject_id


def _timetable(client: TestClient, record_id: int, *, teacher_id: int | None = None) -> None:
    """Every lesson of the record gets a Schedule row (no slot), so the
    record's timetable 'uses' its classes, subjects and the teacher."""
    response = client.post(f"{VERSIONS}/{record_id}/generate-lessons")
    assert response.status_code == 200, response.json()
    db = db_of(client)
    lesson_ids = [lesson["lesson_id"] for lesson in response.json()["created_lessons"]]
    for lesson_id in lesson_ids:
        db.add(Schedule(schedule_version_id=record_id, lesson_id=lesson_id, teacher_id=teacher_id))
    db.commit()


# --- 班級停用 ---


def test_class_is_active_by_default(client: TestClient) -> None:
    grade_id = create_grade(client, level=1)
    response = client.post(
        f"{CLASSES}/", json={"grade_id": grade_id, "name_style": "HEAVENLY_STEM", "name": "一年甲班"}
    )
    assert response.json()["is_active"] is True


def test_existing_rows_default_to_active(client: TestClient) -> None:
    """The migration's server default: a row written without is_active."""
    grade_id = create_grade(client, level=1)
    db = db_of(client)
    db.execute(
        text("INSERT INTO classes (grade_id, name, name_style, created_at, updated_at) "
             "VALUES (:grade, '一年丙班', 'HEAVENLY_STEM', now(), now())"),
        {"grade": grade_id},
    )
    db.commit()
    rows = client.get(f"{CLASSES}/", params={"grade_id": grade_id}).json()
    assert [row["is_active"] for row in rows] == [True]


def test_deactivate_and_activate_class(client: TestClient) -> None:
    grade_id = create_grade(client, level=1)
    class_id = create_class(client, grade_id, "一年甲班")

    deactivated = client.post(f"{CLASSES}/{class_id}/deactivate")
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    activated = client.post(f"{CLASSES}/{class_id}/activate")
    assert activated.json()["is_active"] is True


def test_class_activation_needs_a_coordinator(teacher_client: TestClient, client: TestClient) -> None:
    class_id = create_class(client, create_grade(client, level=1), "一年甲班")
    assert teacher_client.post(f"{CLASSES}/{class_id}/deactivate").status_code == 403


def test_unused_class_is_deleted(client: TestClient) -> None:
    class_id = create_class(client, create_grade(client, level=1), "一年甲班")
    assert client.delete(f"{CLASSES}/{class_id}").status_code == 204


def test_class_in_use_is_409_with_record_count(client: TestClient) -> None:
    _, first, _, _ = _school(client)
    semester_id = _semester(client)
    for _ in range(2):
        _sync(client, create_record(client, semester_id))

    response = client.delete(f"{CLASSES}/{first}")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "CLASS_IN_USE"
    assert body["record_count"] == 2
    assert client.get(f"{CLASSES}/{first}").status_code == 200


def test_sync_leaves_out_inactive_class(client: TestClient) -> None:
    _, first, second, subject_id = _school(client)
    record_id = create_record(client, _semester(client))
    client.post(f"{CLASSES}/{second}/deactivate")

    _sync(client, record_id)

    assert _requirement_keys(client, record_id) == {(first, subject_id)}


def test_reactivated_class_comes_back_on_sync(client: TestClient) -> None:
    _, first, second, subject_id = _school(client)
    record_id = create_record(client, _semester(client))
    client.post(f"{CLASSES}/{second}/deactivate")
    _sync(client, record_id)

    client.post(f"{CLASSES}/{second}/activate")
    _sync(client, record_id)

    assert _requirement_keys(client, record_id) == {(first, subject_id), (second, subject_id)}


def test_old_record_keeps_inactive_class(client: TestClient) -> None:
    _, first, second, subject_id = _school(client)
    record_id = create_record(client, _semester(client))
    _sync(client, record_id)
    _timetable(client, record_id)
    mark_status(client, record_id, "AUTO", is_published=True)

    client.post(f"{CLASSES}/{second}/deactivate")

    assert _requirement_keys(client, record_id) == {(first, subject_id), (second, subject_id)}
    assert client.get(f"{CLASSES}/{second}").json()["is_active"] is False


# --- 停用影響 ---


def test_class_impact_counts(client: TestClient) -> None:
    _, first, _, _ = _school(client)
    semester_id = _semester(client)
    published = create_record(client, semester_id)
    _sync(client, published)
    _timetable(client, published)
    mark_status(client, published, "AUTO", is_published=True)
    other = create_record(client, semester_id)
    _sync(client, other)
    _timetable(client, other)
    mark_status(client, other, "MANUAL")
    not_scheduled = create_record(client, semester_id)
    _sync(client, not_scheduled)

    response = client.get(f"{CLASSES}/{first}/deactivation-impact")

    assert response.status_code == 200
    assert response.json() == {
        "published_records": 1,
        "other_records": 1,
        "not_scheduled_records": 1,
        "grade_requirements": 0,
    }


def test_subject_impact_counts_grade_requirements(client: TestClient) -> None:
    _, _, _, subject_id = _school(client)
    response = client.get(f"/api/v1/subjects/{subject_id}/deactivation-impact")
    assert response.json() == {
        "published_records": 0,
        "other_records": 0,
        "not_scheduled_records": 0,
        "grade_requirements": 1,
    }


def test_teacher_account_impact_counts_settings_and_timetable(client: TestClient) -> None:
    _school(client)
    teacher_id = create_teacher(client, "王老師")
    semester_id = _semester(client)
    used = create_record(client, semester_id)
    _sync(client, used)
    _timetable(client, used, teacher_id=teacher_id)
    mark_status(client, used, "AUTO")
    settings = create_record(client, semester_id)
    client.put(
        f"{VERSIONS}/{settings}/teachers",
        json={"teachers": [{"teacher_id": teacher_id, "min_weekly_periods": 0,
                            "max_weekly_periods": 20, "unavailable_time_slot_ids": []}]},
    )
    users = client.get("/api/v1/users/").json()
    user_id = next(user["id"] for user in users if user.get("teacher_id") == teacher_id)

    response = client.get(f"/api/v1/users/{user_id}/deactivation-impact")

    assert response.json() == {
        "published_records": 0,
        "other_records": 1,
        "not_scheduled_records": 1,
        "grade_requirements": 0,
    }


def test_impact_is_refused_to_a_teacher(client: TestClient, teacher_client: TestClient) -> None:
    _, first, _, subject_id = _school(client)
    room_id = client.post("/api/v1/rooms/", json={"name": "音樂教室"}).json()["id"]
    assert teacher_client.get(f"{CLASSES}/{first}/deactivation-impact").status_code == 403
    assert teacher_client.get(f"/api/v1/subjects/{subject_id}/deactivation-impact").status_code == 403
    assert teacher_client.get(f"/api/v1/rooms/{room_id}/deactivation-impact").status_code == 403
    assert teacher_client.get("/api/v1/users/1/deactivation-impact").status_code == 403


# --- 科目停用 ---


def test_sync_skips_inactive_subject_and_names_it(client: TestClient) -> None:
    grade_id, first, second, chinese = _school(client)
    music = _subject(client, "音樂")
    _rule(client, grade_id, music, 1)
    record_id = create_record(client, _semester(client))
    client.patch(f"/api/v1/subjects/{music}", json={"is_active": False})

    result = _sync(client, record_id)

    assert result["skipped_subjects"] == [{"id": music, "name": "音樂"}]
    assert _requirement_keys(client, record_id) == {(first, chinese), (second, chinese)}


def test_reactivated_subject_comes_back_on_sync(client: TestClient) -> None:
    grade_id, first, second, chinese = _school(client)
    music = _subject(client, "音樂")
    _rule(client, grade_id, music, 1)
    record_id = create_record(client, _semester(client))
    client.patch(f"/api/v1/subjects/{music}", json={"is_active": False})
    _sync(client, record_id)

    client.patch(f"/api/v1/subjects/{music}", json={"is_active": True})
    result = _sync(client, record_id)

    assert result["skipped_subjects"] == []
    assert (first, music) in _requirement_keys(client, record_id)


def test_grade_requirements_hide_inactive_subject(client: TestClient) -> None:
    grade_id, _, _, chinese = _school(client)
    music = _subject(client, "音樂")
    _rule(client, grade_id, music, 1)
    client.patch(f"/api/v1/subjects/{music}", json={"is_active": False})

    shown = client.get(f"{RULES}/", params={"grade_id": grade_id}).json()
    everything = client.get(f"{RULES}/", params={"grade_id": grade_id, "include_inactive": True}).json()

    assert [row["subject_id"] for row in shown] == [chinese]
    assert sorted(row["subject_id"] for row in everything) == sorted([chinese, music])

    client.patch(f"/api/v1/subjects/{music}", json={"is_active": True})
    assert len(client.get(f"{RULES}/", params={"grade_id": grade_id}).json()) == 2


def test_inactive_subject_leaves_old_records_unchanged(client: TestClient) -> None:
    _, first, second, chinese = _school(client)
    record_id = create_record(client, _semester(client))
    _sync(client, record_id)
    _timetable(client, record_id)
    mark_status(client, record_id, "AUTO", is_published=True)
    db = db_of(client)
    rows_before = db.scalar(select(func.count(Schedule.id)).where(Schedule.schedule_version_id == record_id))

    client.patch(f"/api/v1/subjects/{chinese}", json={"is_active": False})

    assert _requirement_keys(client, record_id) == {(first, chinese), (second, chinese)}
    assert db.scalar(
        select(func.count(Schedule.id)).where(Schedule.schedule_version_id == record_id)
    ) == rows_before


# --- 排課前檢查 ---


def test_preflight_writes_nothing(client: TestClient) -> None:
    _school(client)
    record_id = create_record(client, _semester(client))
    _sync(client, record_id)
    db = db_of(client)

    response = client.get(f"{VERSIONS}/{record_id}/preflight")

    assert response.status_code == 200
    assert db.scalar(select(func.count(Lesson.id))) == 0
    assert db.scalar(select(func.count(Schedule.id))) == 0


def test_preflight_reports_a_lesson_without_any_teacher(client: TestClient) -> None:
    _school(client)
    record_id = create_record(client, _semester(client))
    _sync(client, record_id)

    body = client.get(f"{VERSIONS}/{record_id}/preflight").json()

    # No teacher takes part: every (not yet generated) lesson has none.
    assert body["can_schedule"] is False
    assert body["lesson_failures"]
    assert all(failure["lesson_id"] is None for failure in body["lesson_failures"])


def test_preflight_reports_inactive_class_still_in_record(client: TestClient) -> None:
    _, _, second, _ = _school(client)
    record_id = create_record(client, _semester(client))
    _sync(client, record_id)
    client.post(f"{CLASSES}/{second}/deactivate")

    body = client.get(f"{VERSIONS}/{record_id}/preflight").json()

    inactive = [v for v in body["violations"] if v["type"] == "INACTIVE_CLASS_IN_RECORD"]
    assert [v["class_id"] for v in inactive] == [second]
