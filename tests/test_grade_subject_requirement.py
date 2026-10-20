"""學校資料 > 科目需求 (GradeSubjectRequirement): weekly periods per grade
and subject, and how the wizard's 科目需求 step copies them into a
semester (POST /class-subject-requirements/sync)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.grade_class import Grade
from app.models.school import School
from app.models.subject import Subject
from tests.api_helpers import create_class, create_grade, create_time_slot
from tests.test_school_isolation import other_school  # noqa: F401 (fixture)

URL = "/api/v1/grade-subject-requirements"
CSR = "/api/v1/class-subject-requirements"


def _subject(client: TestClient, name: str) -> int:
    response = client.post("/api/v1/subjects/", json={"name": name})
    assert response.status_code == 201, response.json()
    subject_id: int = response.json()["id"]
    return subject_id


def _rule(client: TestClient, grade_id: int, subject_id: int, weekly_periods: int) -> int:
    response = client.post(
        f"{URL}/",
        json={"grade_id": grade_id, "subject_id": subject_id, "weekly_periods": weekly_periods},
    )
    assert response.status_code == 201, response.json()
    rule_id: int = response.json()["id"]
    return rule_id


def _semester(client: TestClient, year: int = 115) -> int:
    year_id = client.post("/api/v1/academic-years/", json={"year": year}).json()["id"]
    semester_id: int = client.post(
        "/api/v1/semesters/", json={"academic_year_id": year_id, "number": 1}
    ).json()["id"]
    return semester_id


def _sync(client: TestClient, semester_id: int) -> dict:
    response = client.post(f"{CSR}/sync", json={"semester_id": semester_id})
    assert response.status_code == 200, response.json()
    data: dict = response.json()
    return data


def _requirements(client: TestClient, semester_id: int) -> dict[tuple[int, int], dict]:
    rows = client.get(f"{CSR}/", params={"semester_id": semester_id, "limit": 1000}).json()
    return {(row["class_id"], row["subject_id"]): row for row in rows}


# --- CRUD ---


def test_create_and_list_rules(client: TestClient) -> None:
    grade_id = create_grade(client, "一年級", level=1)
    other_grade = create_grade(client, "二年級", level=2)
    chinese = _subject(client, "國語")

    response = client.post(
        f"{URL}/", json={"grade_id": grade_id, "subject_id": chinese, "weekly_periods": 5}
    )
    _rule(client, other_grade, chinese, 4)

    assert response.status_code == 201
    assert response.json()["weekly_periods"] == 5
    assert len(client.get(f"{URL}/").json()) == 2
    only_first = client.get(f"{URL}/", params={"grade_id": grade_id}).json()
    assert [(row["grade_id"], row["weekly_periods"]) for row in only_first] == [(grade_id, 5)]


@pytest.mark.parametrize("weekly_periods", [0, 7])
def test_weekly_periods_must_be_1_to_6(client: TestClient, weekly_periods: int) -> None:
    grade_id = create_grade(client, level=1)
    subject_id = _subject(client, "數學")

    response = client.post(
        f"{URL}/",
        json={"grade_id": grade_id, "subject_id": subject_id, "weekly_periods": weekly_periods},
    )

    assert response.status_code == 422


def test_same_grade_and_subject_twice_is_409(client: TestClient) -> None:
    grade_id = create_grade(client, level=1)
    subject_id = _subject(client, "數學")
    _rule(client, grade_id, subject_id, 4)

    response = client.post(
        f"{URL}/", json={"grade_id": grade_id, "subject_id": subject_id, "weekly_periods": 3}
    )

    assert response.status_code == 409


def test_update_changes_only_weekly_periods(client: TestClient) -> None:
    grade_id = create_grade(client, level=1)
    subject_id = _subject(client, "數學")
    rule_id = _rule(client, grade_id, subject_id, 4)

    response = client.patch(f"{URL}/{rule_id}", json={"weekly_periods": 3})

    assert response.status_code == 200
    assert response.json()["weekly_periods"] == 3
    assert client.patch(f"{URL}/{rule_id}", json={"weekly_periods": 9}).status_code == 422
    assert client.patch(f"{URL}/999999", json={"weekly_periods": 3}).status_code == 404


def test_delete_rule(client: TestClient) -> None:
    grade_id = create_grade(client, level=1)
    rule_id = _rule(client, grade_id, _subject(client, "數學"), 4)

    assert client.delete(f"{URL}/{rule_id}").status_code == 204
    assert client.get(f"{URL}/").json() == []
    assert client.delete(f"{URL}/{rule_id}").status_code == 404


def test_subject_used_by_a_rule_cannot_be_deleted(client: TestClient) -> None:
    grade_id = create_grade(client, level=1)
    subject_id = _subject(client, "數學")
    _rule(client, grade_id, subject_id, 4)

    assert client.delete(f"/api/v1/subjects/{subject_id}").status_code == 409


def test_rules_are_limited_to_the_school(
    client: TestClient, db_session: Session, other_school: School
) -> None:
    other_grade = Grade(school_id=other_school.id, name="一年級", level=1)
    other_subject = Subject(school_id=other_school.id, name="國語", is_active=True)
    db_session.add_all([other_grade, other_subject])
    db_session.commit()
    own_subject = _subject(client, "國語")

    response = client.post(
        f"{URL}/",
        json={"grade_id": other_grade.id, "subject_id": own_subject, "weekly_periods": 3},
    )

    assert response.status_code == 422
    assert client.get(f"{URL}/").json() == []


def test_teacher_can_read_but_not_write_rules(
    client: TestClient, teacher_client: TestClient
) -> None:
    grade_id = create_grade(client, level=1)
    subject_id = _subject(client, "數學")
    rule_id = _rule(client, grade_id, subject_id, 4)

    assert teacher_client.get(f"{URL}/").status_code == 200
    assert teacher_client.post(
        f"{URL}/", json={"grade_id": grade_id, "subject_id": subject_id, "weekly_periods": 2}
    ).status_code == 403
    assert teacher_client.patch(f"{URL}/{rule_id}", json={"weekly_periods": 2}).status_code == 403
    assert teacher_client.delete(f"{URL}/{rule_id}").status_code == 403


# --- Copying the rules into a semester (the wizard's 科目需求 step) ---


def test_sync_creates_a_requirement_per_class_and_rule(client: TestClient) -> None:
    first = create_grade(client, "一年級", level=1)
    second = create_grade(client, "二年級", level=2)
    first_a = create_class(client, first, "一年甲班")
    first_b = create_class(client, first, "一年乙班")
    second_a = create_class(client, second, "二年甲班")
    chinese, maths = _subject(client, "國語"), _subject(client, "數學")
    _rule(client, first, chinese, 6)
    _rule(client, first, maths, 4)
    _rule(client, second, chinese, 5)
    semester_id = _semester(client)

    result = _sync(client, semester_id)

    assert result == {"created": 5, "updated": 0, "removed": 0, "locked_requirement_ids": []}
    rows = _requirements(client, semester_id)
    assert {key: row["weekly_periods"] for key, row in rows.items()} == {
        (first_a, chinese): 6,
        (first_a, maths): 4,
        (first_b, chinese): 6,
        (first_b, maths): 4,
        (second_a, chinese): 5,
    }
    assert all(
        row["lesson_pattern"] is None
        and row["required_teacher_id"] is None
        and row["required_room_id"] is None
        for row in rows.values()
    )


def test_sync_twice_changes_nothing_the_second_time(client: TestClient) -> None:
    grade_id = create_grade(client, level=1)
    create_class(client, grade_id, "一年甲班")
    _rule(client, grade_id, _subject(client, "國語"), 6)
    semester_id = _semester(client)
    _sync(client, semester_id)

    assert _sync(client, semester_id) == {
        "created": 0, "updated": 0, "removed": 0, "locked_requirement_ids": []
    }


def test_sync_follows_changed_and_removed_rules_but_keeps_wizard_choices(
    client: TestClient,
) -> None:
    grade_id = create_grade(client, level=1)
    class_id = create_class(client, grade_id, "一年甲班")
    chinese, maths, music = _subject(client, "國語"), _subject(client, "數學"), _subject(client, "音樂")
    chinese_rule = _rule(client, grade_id, chinese, 3)
    maths_rule = _rule(client, grade_id, maths, 4)
    music_rule = _rule(client, grade_id, music, 2)
    room_id = client.post("/api/v1/rooms/", json={"name": "音樂教室"}).json()["id"]
    semester_id = _semester(client)
    _sync(client, semester_id)
    rows = _requirements(client, semester_id)
    # The wizard's own choices.
    client.patch(f"{CSR}/{rows[(class_id, chinese)]['id']}", json={"lesson_pattern": "2+1"})
    client.patch(f"{CSR}/{rows[(class_id, maths)]['id']}", json={"lesson_pattern": "2+2"})
    client.patch(f"{CSR}/{rows[(class_id, music)]['id']}", json={"required_room_id": room_id})
    # The school's rules change.
    client.patch(f"{URL}/{chinese_rule}", json={"weekly_periods": 5})  # 2+1 no longer adds up
    client.patch(f"{URL}/{maths_rule}", json={"weekly_periods": 4})  # unchanged
    client.delete(f"{URL}/{music_rule}")

    result = _sync(client, semester_id)

    assert result == {"created": 0, "updated": 1, "removed": 1, "locked_requirement_ids": []}
    rows = _requirements(client, semester_id)
    assert set(rows) == {(class_id, chinese), (class_id, maths)}
    assert rows[(class_id, chinese)]["weekly_periods"] == 5
    assert rows[(class_id, chinese)]["lesson_pattern"] is None
    assert rows[(class_id, maths)]["lesson_pattern"] == "2+2"


def test_sync_trims_the_lessons_of_a_shrunk_requirement(client: TestClient) -> None:
    grade_id = create_grade(client, level=1)
    create_class(client, grade_id, "一年甲班")
    rule_id = _rule(client, grade_id, _subject(client, "國語"), 4)
    semester_id = _semester(client)
    _sync(client, semester_id)
    version_id = client.post(
        "/api/v1/schedule-versions/", json={"semester_id": semester_id, "version_number": 1}
    ).json()["id"]
    client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")
    client.patch(f"{URL}/{rule_id}", json={"weekly_periods": 2})

    _sync(client, semester_id)

    lessons = client.get("/api/v1/lessons/", params={"semester_id": semester_id}).json()
    assert sorted(lesson["sequence_number"] for lesson in lessons) == [1, 2]
    # generate-lessons is in sync again: nothing over-provisioned.
    regenerated = client.post(f"/api/v1/schedule-versions/{version_id}/generate-lessons")
    assert regenerated.status_code == 200, regenerated.json()


def test_sync_leaves_a_locked_requirement_alone(client: TestClient) -> None:
    grade_id = create_grade(client, level=1)
    class_id = create_class(client, grade_id, "一年甲班")
    subject_id = _subject(client, "國語")
    rule_id = _rule(client, grade_id, subject_id, 1)
    semester_id = _semester(client)
    _sync(client, semester_id)
    requirement_id = _requirements(client, semester_id)[(class_id, subject_id)]["id"]
    teacher = client.post(
        "/api/v1/auth/register",
        json={"username": "t-sync", "password": "teacher-pass-123", "role": "TEACHER", "teacher_name": "王老師"},
    ).json()["id"]
    teacher_id = next(
        row["id"] for row in client.get("/api/v1/teachers/").json() if row["user_id"] == teacher
    )
    slot_id = create_time_slot(client, 1, 1)
    version_id = client.post(
        "/api/v1/schedule-versions/", json={"semester_id": semester_id, "version_number": 1}
    ).json()["id"]
    lesson_id = client.post(
        f"/api/v1/schedule-versions/{version_id}/generate-lessons"
    ).json()["created_lessons"][0]["lesson_id"]
    client.post(
        "/api/v1/schedules/",
        json={
            "schedule_version_id": version_id,
            "lesson_id": lesson_id,
            "teacher_id": teacher_id,
            "time_slot_id": slot_id,
        },
    )
    published = client.patch(f"/api/v1/schedule-versions/{version_id}", json={"status": "PUBLISHED"})
    assert published.status_code == 200, published.json()
    client.patch(f"{URL}/{rule_id}", json={"weekly_periods": 3})

    result = _sync(client, semester_id)

    assert result["locked_requirement_ids"] == [requirement_id]
    assert result["updated"] == 0
    assert _requirements(client, semester_id)[(class_id, subject_id)]["weekly_periods"] == 1


def test_sync_unknown_semester_is_404(client: TestClient) -> None:
    response = client.post(f"{CSR}/sync", json={"semester_id": 999999})

    assert response.status_code == 404


def test_teacher_cannot_sync(client: TestClient, teacher_client: TestClient) -> None:
    semester_id = _semester(client)

    response = teacher_client.post(f"{CSR}/sync", json={"semester_id": semester_id})

    assert response.status_code == 403
