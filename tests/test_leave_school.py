"""帳號改版: 教學組長's 離校 -- their school's 一般老師 becomes 無所屬學校
until the 系統管理員 assigns a school. The old school keeps the teacher row
(old timetables still show the name) but it is out of scheduling."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.school import School
from app.models.teacher import Teacher
from app.models.user import User
from app.services.mailer import AccountMail
from tests.api_helpers import enroll_teacher
from tests.conftest import make_record

USERS_URL = "/api/v1/users/"


def _create_teacher(coordinator_client: TestClient, email: str, name: str) -> dict:
    response = coordinator_client.post(USERS_URL, json={"email": email, "teacher_name": name})
    assert response.status_code == 201, response.text
    return response.json()["user"]


def _password(mail: AccountMail) -> str:
    line = next(line for line in mail.body.splitlines() if line.startswith("密碼："))
    return line.removeprefix("密碼：")


def _token_client(client: TestClient, username: str, password: str) -> TestClient:
    response = client.post(
        "/api/v1/auth/login", data={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return TestClient(client.app, headers={"Authorization": f"Bearer {token}"})


def _record_id(coordinator_client: TestClient, db_session: Session) -> int:
    year_id = coordinator_client.post("/api/v1/academic-years/", json={"year": 115}).json()["id"]
    semester_id = coordinator_client.post(
        "/api/v1/semesters/", json={"academic_year_id": year_id, "number": 1}
    ).json()["id"]
    return make_record(db_session, semester_id).id


def _rows(db_session: Session, user_id: int) -> list[Teacher]:
    db_session.expire_all()
    stmt = select(Teacher).where(Teacher.user_id == user_id).order_by(Teacher.id)
    return list(db_session.scalars(stmt).all())


def test_leave_school_makes_teacher_unassigned(
    coordinator_client: TestClient, db_session: Session, account_school: School
) -> None:
    user = _create_teacher(coordinator_client, "t1@example.com", "王老師")

    response = coordinator_client.post(f"/api/v1/users/{user['id']}/leave-school")

    assert response.status_code == 200, response.text
    assert response.json()["school_id"] is None
    assert response.json()["teacher_id"] is None
    assert response.json()["teacher_name"] == "王老師"
    (row,) = _rows(db_session, user["id"])
    assert row.school_id == account_school.id
    assert row.has_left is True and row.is_active is False
    # No longer in the 教學組長's account list.
    assert [item["id"] for item in coordinator_client.get(USERS_URL).json()] == []


def test_left_teacher_stays_readable_but_inactive(
    coordinator_client: TestClient,
) -> None:
    user = _create_teacher(coordinator_client, "t1@example.com", "王老師")
    teacher_id = next(
        t["id"]
        for t in coordinator_client.get("/api/v1/teachers/", params={"limit": 1000}).json()
        if t["user_id"] == user["id"]
    )
    coordinator_client.post(f"/api/v1/users/{user['id']}/leave-school")

    response = coordinator_client.get(f"/api/v1/teachers/{teacher_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "王老師"
    assert response.json()["has_left"] is True
    assert response.json()["is_active"] is False


def test_left_teacher_cannot_join_new_scheduling(
    coordinator_client: TestClient, db_session: Session, account_school: School
) -> None:
    user = _create_teacher(coordinator_client, "t1@example.com", "王老師")
    (row,) = _rows(db_session, user["id"])
    coordinator_client.post(f"/api/v1/users/{user['id']}/leave-school")
    record_id = _record_id(coordinator_client, db_session)

    response = coordinator_client.put(
        f"/api/v1/schedule-versions/{record_id}/teachers",
        json={
            "teachers": [
                {
                    "teacher_id": row.id,
                    "min_weekly_periods": 0,
                    "max_weekly_periods": 10,
                    "unavailable_time_slot_ids": [],
                }
            ]
        },
    )

    assert response.status_code == 409


def test_leaving_keeps_existing_record_settings(
    coordinator_client: TestClient, db_session: Session, account_school: School
) -> None:
    user = _create_teacher(coordinator_client, "t1@example.com", "王老師")
    (row,) = _rows(db_session, user["id"])
    record_id = _record_id(coordinator_client, db_session)
    enroll_teacher(coordinator_client, record_id, row.id)

    coordinator_client.post(f"/api/v1/users/{user['id']}/leave-school")

    entries = coordinator_client.get(f"/api/v1/schedule-versions/{record_id}/teachers").json()
    assert [entry["teacher_id"] for entry in entries] == [row.id]


def test_unassigned_teacher_logs_in_but_gets_no_school_data(
    coordinator_client: TestClient, sent_mails: list[AccountMail]
) -> None:
    user = _create_teacher(coordinator_client, "t1@example.com", "王老師")
    coordinator_client.post(f"/api/v1/users/{user['id']}/leave-school")

    teacher_client = _token_client(coordinator_client, "t1@example.com", _password(sent_mails[0]))
    profile = teacher_client.get("/api/v1/me")
    records = teacher_client.get("/api/v1/schedule-versions/")

    assert profile.status_code == 200
    assert profile.json()["school_id"] is None
    assert profile.json()["school_name"] is None
    assert profile.json()["name"] == "王老師"
    assert records.status_code == 403
    assert records.json()["detail"] == "目前無所屬學校，請聯絡系統管理員"


def test_admin_assigns_unassigned_teacher_to_new_school(
    coordinator_client: TestClient,
    admin_client: TestClient,
    db_session: Session,
    account_school: School,
) -> None:
    new_school = School(name="新學校", is_active=True)
    db_session.add(new_school)
    db_session.commit()
    user = _create_teacher(coordinator_client, "t1@example.com", "王老師")
    coordinator_client.post(f"/api/v1/users/{user['id']}/leave-school")

    response = admin_client.patch(
        f"/api/v1/users/{user['id']}", json={"school_id": new_school.id}
    )

    assert response.status_code == 200
    assert response.json()["school_id"] == new_school.id
    old_row, new_row = _rows(db_session, user["id"])
    assert old_row.school_id == account_school.id and old_row.has_left is True
    assert new_row.school_id == new_school.id and new_row.has_left is False
    assert new_row.name == "王老師" and new_row.is_active is True


def test_admin_lists_unassigned_teacher(
    coordinator_client: TestClient, admin_client: TestClient
) -> None:
    user = _create_teacher(coordinator_client, "t1@example.com", "王老師")
    coordinator_client.post(f"/api/v1/users/{user['id']}/leave-school")

    items = {item["id"]: item for item in admin_client.get(USERS_URL).json()}

    assert items[user["id"]]["school_id"] is None
    assert items[user["id"]]["teacher_name"] == "王老師"


def test_only_coordinator_may_leave_school(
    coordinator_client: TestClient, admin_client: TestClient, teacher_client: TestClient
) -> None:
    user = _create_teacher(coordinator_client, "t1@example.com", "王老師")

    admin_response = admin_client.post(f"/api/v1/users/{user['id']}/leave-school")
    teacher_response = teacher_client.post(f"/api/v1/users/{user['id']}/leave-school")

    assert admin_response.status_code == 403
    assert teacher_response.status_code == 403


def test_coordinator_cannot_make_coordinator_leave(
    coordinator_client: TestClient, coordinator_user: User
) -> None:
    response = coordinator_client.post(f"/api/v1/users/{coordinator_user.id}/leave-school")

    assert response.status_code == 404
