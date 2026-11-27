import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.grade_class import Class, Grade
from app.models.grade_subject_requirement import GradeSubjectRequirement
from app.models.subject import Subject
from app.models.time_slot import TimeSlot


def test_create_school(admin_client: TestClient) -> None:
    response = admin_client.post("/api/v1/schools/", json={"name": "Test School"})

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test School"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_school_cannot_set_is_active(admin_client: TestClient) -> None:
    response = admin_client.post(
        "/api/v1/schools/", json={"name": "Test School", "is_active": False}
    )

    assert response.status_code == 201
    assert response.json()["is_active"] is True


def test_get_school_list(admin_client: TestClient) -> None:
    admin_client.post("/api/v1/schools/", json={"name": "List Test School"})

    response = admin_client.get("/api/v1/schools/")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "List Test School" in names


def test_get_school_by_id(admin_client: TestClient) -> None:
    create_response = admin_client.post(
        "/api/v1/schools/", json={"name": "Get Test School"}
    )
    school_id = create_response.json()["id"]

    response = admin_client.get(f"/api/v1/schools/{school_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Get Test School"


def test_get_school_not_found(admin_client: TestClient) -> None:
    response = admin_client.get("/api/v1/schools/999999")

    assert response.status_code == 404


def test_update_school(admin_client: TestClient) -> None:
    create_response = admin_client.post("/api/v1/schools/", json={"name": "Old Name"})
    school_id = create_response.json()["id"]

    response = admin_client.patch(
        f"/api/v1/schools/{school_id}", json={"name": "New Name"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_update_school_not_found(admin_client: TestClient) -> None:
    response = admin_client.patch("/api/v1/schools/999999", json={"name": "Nope"})

    assert response.status_code == 404


def test_delete_school(admin_client: TestClient) -> None:
    create_response = admin_client.post("/api/v1/schools/", json={"name": "Delete Me"})
    school_id = create_response.json()["id"]

    response = admin_client.delete(f"/api/v1/schools/{school_id}")

    assert response.status_code == 204


def test_delete_school_not_found(admin_client: TestClient) -> None:
    response = admin_client.delete("/api/v1/schools/999999")

    assert response.status_code == 404


# --- School type and the structure built with the school ---


def _structure(db_session: Session, school_id: int) -> tuple[list[tuple[int, str]], list[TimeSlot]]:
    grades = db_session.execute(
        select(Grade.level, Grade.name).where(Grade.school_id == school_id).order_by(Grade.level)
    ).all()
    slots = list(
        db_session.scalars(
            select(TimeSlot)
            .where(TimeSlot.school_id == school_id)
            .order_by(TimeSlot.weekday, TimeSlot.period)
        ).all()
    )
    return [(level, name) for level, name in grades], slots


def test_create_school_defaults_to_elementary(admin_client: TestClient) -> None:
    response = admin_client.post("/api/v1/schools/", json={"name": "預設國小"})

    assert response.status_code == 201
    assert response.json()["school_type"] == "ELEMENTARY"


def test_create_elementary_school_builds_grades_and_time_slots(
    admin_client: TestClient, db_session: Session
) -> None:
    school_id = admin_client.post(
        "/api/v1/schools/", json={"name": "北湖國小", "school_type": "ELEMENTARY"}
    ).json()["id"]

    grades, slots = _structure(db_session, school_id)

    assert grades == [
        (1, "一年級"), (2, "二年級"), (3, "三年級"), (4, "四年級"), (5, "五年級"), (6, "六年級")
    ]
    assert len(slots) == 5 * 10
    assert {slot.weekday for slot in slots} == {1, 2, 3, 4, 5}
    assert {slot.period for slot in slots} == set(range(0, 10))
    closed = {(slot.period, slot.label) for slot in slots if not slot.is_teaching_period}
    assert closed == {(0, "早自習"), (5, "午休"), (9, "放學")}
    assert all(slot.label is None for slot in slots if slot.is_teaching_period)


@pytest.mark.parametrize(
    ("school_type", "levels", "names"),
    [
        ("JUNIOR_HIGH", [7, 8, 9], ["七年級", "八年級", "九年級"]),
        ("SENIOR_HIGH", [10, 11, 12], ["一年級", "二年級", "三年級"]),
    ],
)
def test_create_secondary_school_builds_its_grades_and_periods_0_to_10(
    admin_client: TestClient,
    db_session: Session,
    school_type: str,
    levels: list[int],
    names: list[str],
) -> None:
    response = admin_client.post(
        "/api/v1/schools/", json={"name": "中學", "school_type": school_type}
    )
    assert response.status_code == 201
    assert response.json()["school_type"] == school_type

    grades, slots = _structure(db_session, response.json()["id"])

    assert grades == list(zip(levels, names))
    assert len(slots) == 5 * 11
    assert {slot.period for slot in slots} == set(range(0, 11))
    closed = {(slot.period, slot.label) for slot in slots if not slot.is_teaching_period}
    assert closed == {(0, "早自習"), (5, "午休"), (10, "放學")}


def test_create_school_unknown_type_is_422(admin_client: TestClient) -> None:
    response = admin_client.post(
        "/api/v1/schools/", json={"name": "大學", "school_type": "UNIVERSITY"}
    )

    assert response.status_code == 422


def test_school_type_cannot_be_changed(admin_client: TestClient) -> None:
    school_id = admin_client.post(
        "/api/v1/schools/", json={"name": "國小", "school_type": "ELEMENTARY"}
    ).json()["id"]

    response = admin_client.patch(
        f"/api/v1/schools/{school_id}", json={"school_type": "SENIOR_HIGH"}
    )

    assert response.status_code == 200
    assert response.json()["school_type"] == "ELEMENTARY"


def test_delete_school_takes_its_built_structure_with_it(
    admin_client: TestClient, db_session: Session
) -> None:
    school_id = admin_client.post("/api/v1/schools/", json={"name": "刪除國小"}).json()["id"]

    assert admin_client.delete(f"/api/v1/schools/{school_id}").status_code == 204

    assert _structure(db_session, school_id) == ([], [])


def test_delete_school_with_classes_is_409_and_keeps_everything(
    admin_client: TestClient, db_session: Session
) -> None:
    school_id = admin_client.post("/api/v1/schools/", json={"name": "有班級國小"}).json()["id"]
    grade = db_session.scalars(select(Grade).where(Grade.school_id == school_id)).first()
    assert grade is not None
    db_session.add(Class(grade_id=grade.id, name="一年甲班"))
    db_session.commit()

    response = admin_client.delete(f"/api/v1/schools/{school_id}")

    assert response.status_code == 409
    grades, slots = _structure(db_session, school_id)
    assert len(grades) == 6
    assert len(slots) == 50


def _subjects_and_periods(
    db_session: Session, school_id: int
) -> tuple[list[str], dict[int, dict[str, int]]]:
    """The school's subject names (by id) and, per grade level, each
    subject's weekly periods (學校資料 > 科目需求)."""
    subjects = db_session.scalars(
        select(Subject).where(Subject.school_id == school_id).order_by(Subject.id)
    ).all()
    name_of = {subject.id: subject.name for subject in subjects}
    periods: dict[int, dict[str, int]] = {}
    for level, subject_id, weekly_periods in db_session.execute(
        select(Grade.level, GradeSubjectRequirement.subject_id, GradeSubjectRequirement.weekly_periods)
        .join(Grade, GradeSubjectRequirement.grade_id == Grade.id)
        .where(Grade.school_id == school_id)
    ).all():
        periods.setdefault(level, {})[name_of[subject_id]] = weekly_periods
    return [subject.name for subject in subjects], periods


def test_create_elementary_school_builds_default_subjects_and_periods(
    admin_client: TestClient, db_session: Session
) -> None:
    """v3: a new 國小 starts with the ten 領域 and every grade's weekly
    periods of them."""
    school_id = admin_client.post("/api/v1/schools/", json={"name": "預設科目國小"}).json()["id"]

    names, periods = _subjects_and_periods(db_session, school_id)

    assert names == [
        "國語文", "英語文", "本土語文／臺灣手語", "數學", "生活課程",
        "社會", "自然科學", "藝術", "健康與體育", "綜合活動",
    ]
    lower = {"國語文": 6, "本土語文／臺灣手語": 1, "數學": 4, "生活課程": 6, "健康與體育": 3}
    middle = {
        "國語文": 5, "本土語文／臺灣手語": 1, "英語文": 1, "數學": 4, "社會": 3,
        "自然科學": 3, "藝術": 3, "綜合活動": 2, "健康與體育": 3,
    }
    upper = {**middle, "英語文": 2}
    assert periods == {1: lower, 2: lower, 3: middle, 4: middle, 5: upper, 6: upper}


@pytest.mark.parametrize("school_type", ["JUNIOR_HIGH", "SENIOR_HIGH"])
def test_create_secondary_school_has_no_default_subjects(
    admin_client: TestClient, db_session: Session, school_type: str
) -> None:
    school_id = admin_client.post(
        "/api/v1/schools/", json={"name": "中學", "school_type": school_type}
    ).json()["id"]

    assert _subjects_and_periods(db_session, school_id) == ([], {})


def test_delete_school_takes_its_default_subjects_with_it(
    admin_client: TestClient, db_session: Session
) -> None:
    school_id = admin_client.post("/api/v1/schools/", json={"name": "刪除國小"}).json()["id"]

    assert admin_client.delete(f"/api/v1/schools/{school_id}").status_code == 204

    assert _subjects_and_periods(db_session, school_id) == ([], {})
