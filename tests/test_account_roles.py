from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.school import School
from app.models.teacher import Teacher
from app.models.user import User

# Task 98: three roles. The `admin_client` fixture is the 系統管理員 (ADMIN, no
# school); `coordinator_client` the 教學組長 of `account_school`;
# `teacher_user` an 一般老師 of the same school. `other_school` below is a
# second school the 教學組長 must not reach.

REGISTER_URL = "/api/v1/auth/register"


def _login(admin_client: TestClient, username: str, password: str) -> int:
    response = admin_client.post(
        "/api/v1/auth/login", data={"username": username, "password": password}
    )
    return response.status_code


def _teacher_body(username: str, school_id: int | None = None, name: str = "王老師") -> dict[str, Any]:
    body: dict[str, Any] = {
        "username": username,
        "password": "s3cret-pass",
        "role": "TEACHER",
        "teacher_name": name,
    }
    if school_id is not None:
        body["school_id"] = school_id
    return body


def _make_school(db_session: Session, name: str) -> School:
    school = School(name=name, is_active=True)
    db_session.add(school)
    db_session.commit()
    db_session.refresh(school)
    return school


def _make_teacher_account(db_session: Session, username: str, school: School) -> User:
    user = User(
        username=username,
        hashed_password=hash_password("teacher-pass-123"),
        role="TEACHER",
        is_active=True,
        school_id=school.id,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        Teacher(
            school_id=school.id,
            name=f"{username} 老師",
            is_active=True,
            min_weekly_periods=0,
            max_weekly_periods=0,
            user_id=user.id,
        )
    )
    db_session.commit()
    db_session.refresh(user)
    return user


def _teacher_of(db_session: Session, user_id: int) -> Teacher | None:
    db_session.expire_all()
    return db_session.scalars(select(Teacher).where(Teacher.user_id == user_id)).first()


# --- creating accounts: 系統管理員 ---


def test_admin_creates_coordinator_for_school(
    admin_client: TestClient, account_school: School
) -> None:
    response = admin_client.post(
        REGISTER_URL,
        json={
            "username": "coord2",
            "password": "s3cret-pass",
            "role": "COORDINATOR",
            "school_id": account_school.id,
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "COORDINATOR"
    assert response.json()["school_id"] == account_school.id


def test_admin_creating_coordinator_without_school_returns_403(
    admin_client: TestClient,
) -> None:
    response = admin_client.post(
        REGISTER_URL,
        json={"username": "coord2", "password": "s3cret-pass", "role": "COORDINATOR"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "教學組長與一般老師帳號必須指定所屬學校"


def test_admin_account_with_school_returns_403(
    admin_client: TestClient, account_school: School
) -> None:
    response = admin_client.post(
        REGISTER_URL,
        json={
            "username": "admin2",
            "password": "s3cret-pass",
            "role": "ADMIN",
            "school_id": account_school.id,
        },
    )

    assert response.status_code == 403


def test_account_with_unknown_school_returns_422(admin_client: TestClient) -> None:
    response = admin_client.post(REGISTER_URL, json=_teacher_body("t1", school_id=999999))

    assert response.status_code == 422


def test_teacher_account_creates_its_teacher(
    admin_client: TestClient, db_session: Session, account_school: School
) -> None:
    response = admin_client.post(
        REGISTER_URL, json=_teacher_body("t1", account_school.id, name="  林老師 ")
    )

    assert response.status_code == 201
    teacher = _teacher_of(db_session, response.json()["id"])
    assert teacher is not None
    assert teacher.name == "林老師"
    assert teacher.school_id == account_school.id
    assert teacher.is_active is True


def test_teacher_account_without_name_returns_422(
    admin_client: TestClient, db_session: Session, account_school: School
) -> None:
    body = _teacher_body("t1", account_school.id)
    del body["teacher_name"]

    response = admin_client.post(REGISTER_URL, json=body)

    assert response.status_code == 422
    assert db_session.scalars(select(User).where(User.username == "t1")).first() is None


# --- creating accounts: 教學組長 ---


def test_coordinator_creates_teacher_in_own_school(
    coordinator_client: TestClient, db_session: Session, account_school: School
) -> None:
    response = coordinator_client.post(REGISTER_URL, json=_teacher_body("t1"))

    assert response.status_code == 201
    assert response.json()["school_id"] == account_school.id
    assert _teacher_of(db_session, response.json()["id"]) is not None


def test_coordinator_cannot_create_coordinator_or_admin(
    coordinator_client: TestClient, account_school: School
) -> None:
    coordinator_response = coordinator_client.post(
        REGISTER_URL,
        json={
            "username": "coord2",
            "password": "s3cret-pass",
            "role": "COORDINATOR",
            "school_id": account_school.id,
        },
    )
    admin_response = coordinator_client.post(
        REGISTER_URL,
        json={"username": "admin2", "password": "s3cret-pass", "role": "ADMIN"},
    )

    assert coordinator_response.status_code == 403
    assert coordinator_response.json()["detail"] == "教學組長只能建立一般老師帳號"
    assert admin_response.status_code == 403


def test_coordinator_cannot_create_teacher_in_other_school(
    coordinator_client: TestClient, db_session: Session
) -> None:
    other_school = _make_school(db_session, "別的學校")

    response = coordinator_client.post(
        REGISTER_URL, json=_teacher_body("t1", other_school.id)
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "教學組長只能管理自己學校的帳號"


def test_teacher_cannot_register_accounts(teacher_client: TestClient) -> None:
    response = teacher_client.post(REGISTER_URL, json=_teacher_body("t1"))

    assert response.status_code == 403


# --- listing ---


def test_coordinator_lists_only_own_school_teachers(
    coordinator_client: TestClient,
    db_session: Session,
    admin_user: User,
    account_school: School,
) -> None:
    other_school = _make_school(db_session, "別的學校")
    own = _make_teacher_account(db_session, "own_teacher", account_school)
    _make_teacher_account(db_session, "other_teacher", other_school)

    response = coordinator_client.get("/api/v1/users/")

    assert response.status_code == 200
    data = response.json()
    assert [item["username"] for item in data] == ["own_teacher"]
    assert data[0]["id"] == own.id
    assert data[0]["teacher_name"] == "own_teacher 老師"


def test_admin_lists_every_account(
    admin_client: TestClient, db_session: Session, coordinator_user: User
) -> None:
    other_school = _make_school(db_session, "別的學校")
    _make_teacher_account(db_session, "other_teacher", other_school)

    response = admin_client.get("/api/v1/users/")

    assert [item["username"] for item in response.json()] == [
        "admin_test",
        "coordinator_test",
        "other_teacher",
    ]


# --- 停用 / 啟用 ---


def test_coordinator_deactivates_own_school_teacher(
    coordinator_client: TestClient, db_session: Session, account_school: School
) -> None:
    user = _make_teacher_account(db_session, "own_teacher", account_school)

    response = coordinator_client.patch(
        f"/api/v1/users/{user.id}", json={"is_active": False}
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    teacher = _teacher_of(db_session, user.id)
    assert teacher is not None and teacher.is_active is False
    assert _login(coordinator_client, "own_teacher", "teacher-pass-123") == 401


def test_reactivating_restores_teacher(
    coordinator_client: TestClient, db_session: Session, account_school: School
) -> None:
    user = _make_teacher_account(db_session, "own_teacher", account_school)
    coordinator_client.patch(f"/api/v1/users/{user.id}", json={"is_active": False})

    response = coordinator_client.patch(
        f"/api/v1/users/{user.id}", json={"is_active": True}
    )

    assert response.status_code == 200
    teacher = _teacher_of(db_session, user.id)
    assert teacher is not None and teacher.is_active is True
    assert _login(coordinator_client, "own_teacher", "teacher-pass-123") == 200


def test_coordinator_cannot_touch_other_school_teacher(
    coordinator_client: TestClient, db_session: Session
) -> None:
    other_school = _make_school(db_session, "別的學校")
    user = _make_teacher_account(db_session, "other_teacher", other_school)

    deactivate_response = coordinator_client.patch(
        f"/api/v1/users/{user.id}", json={"is_active": False}
    )
    reset_response = coordinator_client.patch(
        f"/api/v1/users/{user.id}/password", json={"password": "brand-new-pass"}
    )

    assert deactivate_response.status_code == 404
    assert reset_response.status_code == 404
    assert _login(coordinator_client, "other_teacher", "teacher-pass-123") == 200


def test_coordinator_cannot_touch_admin(
    coordinator_client: TestClient, admin_user: User
) -> None:
    response = coordinator_client.patch(
        f"/api/v1/users/{admin_user.id}", json={"is_active": False}
    )

    assert response.status_code == 404


def test_cannot_deactivate_self(admin_client: TestClient, admin_user: User) -> None:
    response = admin_client.patch(f"/api/v1/users/{admin_user.id}", json={"is_active": False})

    assert response.status_code == 403
    assert response.json()["detail"] == "不能停用目前登入中的帳號"


def test_coordinator_resets_own_school_teacher_password(
    coordinator_client: TestClient, db_session: Session, account_school: School
) -> None:
    user = _make_teacher_account(db_session, "own_teacher", account_school)

    response = coordinator_client.patch(
        f"/api/v1/users/{user.id}/password", json={"password": "brand-new-pass"}
    )

    assert response.status_code == 204
    assert _login(coordinator_client, "own_teacher", "brand-new-pass") == 200


# --- 綁定學校 ---


def test_admin_binds_teacher_to_another_school(
    admin_client: TestClient, db_session: Session, account_school: School
) -> None:
    other_school = _make_school(db_session, "別的學校")
    user = _make_teacher_account(db_session, "own_teacher", account_school)

    response = admin_client.patch(
        f"/api/v1/users/{user.id}", json={"school_id": other_school.id}
    )

    assert response.status_code == 200
    assert response.json()["school_id"] == other_school.id
    # The account's Teacher moves with it.
    teacher = _teacher_of(db_session, user.id)
    assert teacher is not None and teacher.school_id == other_school.id


def test_coordinator_cannot_change_school(
    coordinator_client: TestClient, db_session: Session, account_school: School
) -> None:
    other_school = _make_school(db_session, "別的學校")
    user = _make_teacher_account(db_session, "own_teacher", account_school)

    response = coordinator_client.patch(
        f"/api/v1/users/{user.id}", json={"school_id": other_school.id}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "只有系統管理員可以變更帳號所屬的學校"


def test_non_admin_account_cannot_lose_its_school(
    admin_client: TestClient, coordinator_user: User
) -> None:
    response = admin_client.patch(
        f"/api/v1/users/{coordinator_user.id}", json={"school_id": None}
    )

    assert response.status_code == 403


# --- deleting stays ADMIN-only ---


def test_coordinator_cannot_delete_accounts(
    coordinator_client: TestClient, db_session: Session, account_school: School
) -> None:
    user = _make_teacher_account(db_session, "own_teacher", account_school)

    response = coordinator_client.delete(f"/api/v1/users/{user.id}")

    assert response.status_code == 403


def test_deleting_teacher_account_with_teacher_returns_409(
    admin_client: TestClient, db_session: Session, account_school: School
) -> None:
    user = _make_teacher_account(db_session, "own_teacher", account_school)

    response = admin_client.delete(f"/api/v1/users/{user.id}")

    assert response.status_code == 409


# --- scheduling data and schools ---


def test_coordinator_can_write_scheduling_data(coordinator_client: TestClient) -> None:
    response = coordinator_client.post("/api/v1/subjects/", json={"name": "國語"})

    assert response.status_code == 201


def test_coordinator_cannot_create_schools(coordinator_client: TestClient) -> None:
    response = coordinator_client.post("/api/v1/schools/", json={"name": "新學校"})

    assert response.status_code == 403
