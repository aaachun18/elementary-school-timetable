"""帳號改版: who may create, see and change which accounts.

The `admin_client` fixture is the 系統管理員 (ADMIN, no school);
`coordinator_client` the 教學組長 of `account_school`. Accounts created
through POST /api/v1/users/ are emails with a mailed random password (the
autouse `sent_mails` fixture in conftest.py collects the mails)."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.school import School
from app.models.teacher import Teacher
from app.models.user import User
from app.services import mailer
from app.services.mailer import AccountMail

USERS_URL = "/api/v1/users/"


def _login(client: TestClient, username: str, password: str) -> int:
    response = client.post(
        "/api/v1/auth/login", data={"username": username, "password": password}
    )
    return response.status_code


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


def _teachers_of(db_session: Session, user_id: int) -> list[Teacher]:
    db_session.expire_all()
    stmt = select(Teacher).where(Teacher.user_id == user_id).order_by(Teacher.id)
    return list(db_session.scalars(stmt).all())


def _current_teacher(db_session: Session, user_id: int) -> Teacher | None:
    return next((t for t in _teachers_of(db_session, user_id) if not t.has_left), None)


def _password_in(mail: AccountMail) -> str:
    line = next(line for line in mail.body.splitlines() if line.startswith("密碼："))
    return line.removeprefix("密碼：")


# --- creating accounts: 系統管理員 -> 教學組長 only ---


def test_admin_creates_coordinator_with_school_and_email(
    admin_client: TestClient,
    db_session: Session,
    account_school: School,
    sent_mails: list[AccountMail],
) -> None:
    response = admin_client.post(
        USERS_URL, json={"email": " Coord2@Example.com ", "school_id": account_school.id}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["username"] == "coord2@example.com"
    assert body["user"]["role"] == "COORDINATOR"
    assert body["user"]["school_id"] == account_school.id
    assert body["email_sent"] is True
    assert body["initial_password"] is None
    # 教學組長 can be scheduled: they get a teacher row, named after the
    # email until they change it on 個人資料.
    teacher = _current_teacher(db_session, body["user"]["id"])
    assert teacher is not None
    assert teacher.name == "coord2"
    assert teacher.school_id == account_school.id


def test_account_mail_has_email_password_and_text(
    admin_client: TestClient, account_school: School, sent_mails: list[AccountMail]
) -> None:
    admin_client.post(USERS_URL, json={"email": "coord2@example.com", "school_id": account_school.id})

    assert len(sent_mails) == 1
    mail = sent_mails[0]
    assert mail.to == "coord2@example.com"
    assert "帳號：coord2@example.com" in mail.body
    assert "可以至頁面登入，若有需要可以至個人資料維護頁面修改密碼。" in mail.body
    password = _password_in(mail)
    assert len(password) == 8
    assert _login(admin_client, "coord2@example.com", password) == 200


def test_admin_creating_coordinator_without_school_returns_403(
    admin_client: TestClient,
) -> None:
    response = admin_client.post(USERS_URL, json={"email": "coord2@example.com"})

    assert response.status_code == 403
    assert response.json()["detail"] == "教學組長帳號必須指定所屬學校"


def test_admin_cannot_create_teacher_or_admin(
    admin_client: TestClient, db_session: Session, account_school: School
) -> None:
    # Whatever the body says, the 系統管理員's new account is a 教學組長.
    response = admin_client.post(
        USERS_URL,
        json={
            "email": "t1@example.com",
            "school_id": account_school.id,
            "teacher_name": "王老師",
            "role": "ADMIN",
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["role"] == "COORDINATOR"


def test_account_with_unknown_school_returns_422(admin_client: TestClient) -> None:
    response = admin_client.post(USERS_URL, json={"email": "c@example.com", "school_id": 999999})

    assert response.status_code == 422


def test_invalid_email_returns_422(admin_client: TestClient, account_school: School) -> None:
    response = admin_client.post(
        USERS_URL, json={"email": "not-an-email", "school_id": account_school.id}
    )

    assert response.status_code == 422


def test_duplicate_email_returns_409(
    admin_client: TestClient, account_school: School, sent_mails: list[AccountMail]
) -> None:
    body = {"email": "dup@example.com", "school_id": account_school.id}
    assert admin_client.post(USERS_URL, json=body).status_code == 201

    response = admin_client.post(USERS_URL, json={**body, "email": "DUP@example.com"})

    assert response.status_code == 409
    assert len(sent_mails) == 1


def test_mail_failure_keeps_account_and_returns_password(
    admin_client: TestClient, account_school: School, monkeypatch: Any
) -> None:
    monkeypatch.setattr(mailer, "deliver", lambda mail: False)

    response = admin_client.post(
        USERS_URL, json={"email": "coord2@example.com", "school_id": account_school.id}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email_sent"] is False
    assert len(body["initial_password"]) == 8
    assert _login(admin_client, "coord2@example.com", body["initial_password"]) == 200


# --- creating accounts: 教學組長 -> 一般老師 of their school ---


def test_coordinator_creates_teacher_in_own_school(
    coordinator_client: TestClient,
    db_session: Session,
    account_school: School,
    sent_mails: list[AccountMail],
) -> None:
    other_school = _make_school(db_session, "別的學校")

    response = coordinator_client.post(
        USERS_URL,
        json={"email": "t1@example.com", "teacher_name": "  林老師 ", "school_id": other_school.id},
    )

    assert response.status_code == 201, response.text
    user = response.json()["user"]
    assert user["role"] == "TEACHER"
    # school_id in the body is ignored: always the 教學組長's own school.
    assert user["school_id"] == account_school.id
    assert user["teacher_name"] == "林老師"
    teacher = _current_teacher(db_session, user["id"])
    assert teacher is not None and teacher.name == "林老師"
    assert _login(coordinator_client, "t1@example.com", _password_in(sent_mails[0])) == 200


def test_coordinator_teacher_without_name_returns_403(
    coordinator_client: TestClient, db_session: Session
) -> None:
    response = coordinator_client.post(USERS_URL, json={"email": "t1@example.com"})

    assert response.status_code == 403
    assert response.json()["detail"] == "請填寫教師姓名"
    assert db_session.scalars(select(User).where(User.username == "t1@example.com")).first() is None


def test_blank_teacher_name_returns_422(coordinator_client: TestClient) -> None:
    response = coordinator_client.post(
        USERS_URL, json={"email": "t1@example.com", "teacher_name": "   "}
    )

    assert response.status_code == 422


def test_teacher_cannot_create_accounts(teacher_client: TestClient) -> None:
    response = teacher_client.post(
        USERS_URL, json={"email": "t1@example.com", "teacher_name": "王老師"}
    )

    assert response.status_code == 403


def test_same_name_teachers_are_allowed(coordinator_client: TestClient) -> None:
    # 身分證字號 is gone: two teachers of one school may share a name (the
    # account email tells them apart).
    for email in ("wang1@example.com", "wang2@example.com"):
        response = coordinator_client.post(
            USERS_URL, json={"email": email, "teacher_name": "王小明"}
        )
        assert response.status_code == 201


# --- listing and search ---


def test_coordinator_lists_only_own_school_teachers(
    coordinator_client: TestClient,
    db_session: Session,
    admin_user: User,
    account_school: School,
) -> None:
    other_school = _make_school(db_session, "別的學校")
    own = _make_teacher_account(db_session, "own_teacher", account_school)
    _make_teacher_account(db_session, "other_teacher", other_school)

    response = coordinator_client.get(USERS_URL)

    assert response.status_code == 200
    data = response.json()
    assert [item["username"] for item in data] == ["own_teacher"]
    assert data[0]["id"] == own.id
    assert data[0]["teacher_name"] == "own_teacher 老師"


def test_admin_lists_every_account_but_admins(
    admin_client: TestClient, db_session: Session, coordinator_user: User
) -> None:
    other_school = _make_school(db_session, "別的學校")
    _make_teacher_account(db_session, "other_teacher", other_school)

    response = admin_client.get(USERS_URL)

    assert [item["username"] for item in response.json()] == [
        "coordinator_test",
        "other_teacher",
    ]


def test_list_item_fields(admin_client: TestClient, teacher_user: User) -> None:
    item = admin_client.get(USERS_URL).json()[0]

    assert set(item.keys()) == {
        "id",
        "username",
        "role",
        "is_active",
        "school_id",
        "teacher_name",
        "teacher_id",
    }


def _usernames(client: TestClient, search: str | None) -> list[str]:
    params = {} if search is None else {"search": search}
    response = client.get(USERS_URL, params=params)
    assert response.status_code == 200, response.text
    return [user["username"] for user in response.json()]


def _three_teachers(client: TestClient) -> None:
    for email, name in (
        ("wang1@example.com", "王小明"),
        ("wang2@example.com", "王小明"),
        ("chen@example.com", "陳美玲"),
    ):
        assert client.post(USERS_URL, json={"email": email, "teacher_name": name}).status_code == 201


def test_search_by_email_or_name(coordinator_client: TestClient) -> None:
    _three_teachers(coordinator_client)

    assert _usernames(coordinator_client, "WANG") == ["wang1@example.com", "wang2@example.com"]
    assert _usernames(coordinator_client, "美玲") == ["chen@example.com"]
    assert _usernames(coordinator_client, "李") == []
    assert _usernames(coordinator_client, "  ") == [
        "wang1@example.com",
        "wang2@example.com",
        "chen@example.com",
    ]


def test_search_percent_and_underscore_are_plain_characters(
    coordinator_client: TestClient,
) -> None:
    _three_teachers(coordinator_client)

    assert _usernames(coordinator_client, "%") == []
    assert _usernames(coordinator_client, "_") == []


# --- 停用 / 啟用: 系統管理員 only ---


def test_admin_deactivates_and_reactivates_teacher(
    admin_client: TestClient, db_session: Session, account_school: School
) -> None:
    user = _make_teacher_account(db_session, "own_teacher", account_school)

    response = admin_client.patch(f"/api/v1/users/{user.id}", json={"is_active": False})

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    teacher = _current_teacher(db_session, user.id)
    assert teacher is not None and teacher.is_active is False
    assert _login(admin_client, "own_teacher", "teacher-pass-123") == 401

    admin_client.patch(f"/api/v1/users/{user.id}", json={"is_active": True})
    teacher = _current_teacher(db_session, user.id)
    assert teacher is not None and teacher.is_active is True
    assert _login(admin_client, "own_teacher", "teacher-pass-123") == 200


def test_coordinator_cannot_deactivate(
    coordinator_client: TestClient, db_session: Session, account_school: School
) -> None:
    user = _make_teacher_account(db_session, "own_teacher", account_school)

    response = coordinator_client.patch(f"/api/v1/users/{user.id}", json={"is_active": False})

    assert response.status_code == 403
    assert response.json()["detail"] == "只有系統管理員可以停用或啟用帳號"
    assert _login(coordinator_client, "own_teacher", "teacher-pass-123") == 200


def test_coordinator_cannot_touch_other_school_teacher(
    coordinator_client: TestClient, db_session: Session
) -> None:
    other_school = _make_school(db_session, "別的學校")
    user = _make_teacher_account(db_session, "other_teacher", other_school)

    reset_response = coordinator_client.patch(
        f"/api/v1/users/{user.id}/password", json={"password": "brand-new-pass"}
    )
    leave_response = coordinator_client.post(f"/api/v1/users/{user.id}/leave-school")

    assert reset_response.status_code == 404
    assert leave_response.status_code == 404
    assert _login(coordinator_client, "other_teacher", "teacher-pass-123") == 200


def test_coordinator_cannot_touch_admin(
    coordinator_client: TestClient, admin_user: User
) -> None:
    response = coordinator_client.patch(
        f"/api/v1/users/{admin_user.id}/password", json={"password": "brand-new-pass"}
    )

    assert response.status_code == 404


def test_admin_cannot_manage_admin_accounts(
    admin_client: TestClient, admin_user: User
) -> None:
    response = admin_client.patch(f"/api/v1/users/{admin_user.id}", json={"is_active": False})

    assert response.status_code == 404


def test_coordinator_resets_own_school_teacher_password(
    coordinator_client: TestClient, db_session: Session, account_school: School
) -> None:
    user = _make_teacher_account(db_session, "own_teacher", account_school)

    response = coordinator_client.patch(
        f"/api/v1/users/{user.id}/password", json={"password": "brand-new-pass"}
    )

    assert response.status_code == 204
    assert _login(coordinator_client, "own_teacher", "brand-new-pass") == 200


def test_admin_resets_coordinator_password(
    admin_client: TestClient, coordinator_user: User
) -> None:
    response = admin_client.patch(
        f"/api/v1/users/{coordinator_user.id}/password", json={"password": "brand-new-pass"}
    )

    assert response.status_code == 204
    assert _login(admin_client, "coordinator_test", "brand-new-pass") == 200


# --- accounts are never deleted ---


def test_delete_endpoint_does_not_exist(
    admin_client: TestClient, db_session: Session, account_school: School
) -> None:
    user = _make_teacher_account(db_session, "own_teacher", account_school)

    response = admin_client.delete(f"/api/v1/users/{user.id}")

    assert response.status_code == 405
    assert _login(admin_client, "own_teacher", "teacher-pass-123") == 200


# --- 所屬學校: 系統管理員 only ---


def test_admin_moves_teacher_to_another_school(
    admin_client: TestClient, db_session: Session, account_school: School
) -> None:
    other_school = _make_school(db_session, "別的學校")
    user = _make_teacher_account(db_session, "own_teacher", account_school)

    response = admin_client.patch(f"/api/v1/users/{user.id}", json={"school_id": other_school.id})

    assert response.status_code == 200
    assert response.json()["school_id"] == other_school.id
    old_row, new_row = _teachers_of(db_session, user.id)
    # The old school keeps its teacher row (old timetables), marked left.
    assert old_row.school_id == account_school.id
    assert old_row.has_left is True and old_row.is_active is False
    assert new_row.school_id == other_school.id
    assert new_row.has_left is False and new_row.is_active is True
    assert new_row.name == "own_teacher 老師"
    assert response.json()["teacher_id"] == new_row.id


def test_moving_back_to_old_school_restores_old_row(
    admin_client: TestClient, db_session: Session, account_school: School
) -> None:
    other_school = _make_school(db_session, "別的學校")
    user = _make_teacher_account(db_session, "own_teacher", account_school)
    original = _current_teacher(db_session, user.id)
    assert original is not None

    admin_client.patch(f"/api/v1/users/{user.id}", json={"school_id": other_school.id})
    admin_client.patch(f"/api/v1/users/{user.id}", json={"school_id": account_school.id})

    rows = _teachers_of(db_session, user.id)
    assert len(rows) == 2
    current = _current_teacher(db_session, user.id)
    assert current is not None and current.id == original.id


def test_admin_moves_coordinator_to_another_school(
    admin_client: TestClient, db_session: Session, account_school: School
) -> None:
    other_school = _make_school(db_session, "別的學校")
    created = admin_client.post(
        USERS_URL, json={"email": "coord2@example.com", "school_id": account_school.id}
    ).json()["user"]

    response = admin_client.patch(
        f"/api/v1/users/{created['id']}", json={"school_id": other_school.id}
    )

    assert response.status_code == 200
    current = _current_teacher(db_session, created["id"])
    assert current is not None and current.school_id == other_school.id


def test_coordinator_cannot_lose_its_school(
    admin_client: TestClient, coordinator_user: User
) -> None:
    response = admin_client.patch(f"/api/v1/users/{coordinator_user.id}", json={"school_id": None})

    assert response.status_code == 403


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


# --- scheduling data and schools ---


def test_coordinator_can_write_scheduling_data(coordinator_client: TestClient) -> None:
    response = coordinator_client.post("/api/v1/subjects/", json={"name": "國語"})

    assert response.status_code == 201


def test_coordinator_cannot_create_schools(coordinator_client: TestClient) -> None:
    response = coordinator_client.post("/api/v1/schools/", json={"name": "新學校"})

    assert response.status_code == 403
