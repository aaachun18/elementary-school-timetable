"""帳號改版: 個人資料維護 -- GET / PATCH /api/v1/me and PATCH
/api/v1/me/password, for every role."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.school import School
from app.models.user import User
from app.services.mailer import AccountMail

ME_URL = "/api/v1/me"


def _password(mail: AccountMail) -> str:
    line = next(line for line in mail.body.splitlines() if line.startswith("密碼："))
    return line.removeprefix("密碼：")


def _login_client(client: TestClient, username: str, password: str) -> TestClient:
    response = client.post(
        "/api/v1/auth/login", data={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return TestClient(client.app, headers={"Authorization": f"Bearer {token}"})


def test_admin_profile_has_only_account(admin_client: TestClient) -> None:
    response = admin_client.get(ME_URL)

    assert response.status_code == 200
    assert response.json() == {
        "username": "admin_test",
        "role": "ADMIN",
        "school_id": None,
        "school_name": None,
        "name": None,
    }


def test_admin_cannot_set_name(admin_client: TestClient) -> None:
    response = admin_client.patch(ME_URL, json={"name": "管理員"})

    assert response.status_code == 403


def test_coordinator_profile_and_rename(
    admin_client: TestClient,
    account_school: School,
    sent_mails: list[AccountMail],
) -> None:
    admin_client.post("/api/v1/users/", json={"email": "c2@example.com", "school_id": account_school.id})
    coordinator = _login_client(admin_client, "c2@example.com", _password(sent_mails[0]))

    before = coordinator.get(ME_URL).json()
    response = coordinator.patch(ME_URL, json={"name": "  林組長 "})

    assert before["name"] == "c2"
    assert before["school_name"] == account_school.name
    assert response.status_code == 200
    assert response.json()["name"] == "林組長"
    assert response.json()["username"] == "c2@example.com"
    # The name is the teacher row's -- what timetables show.
    names = [t["name"] for t in coordinator.get("/api/v1/teachers/", params={"limit": 1000}).json()]
    assert "林組長" in names


def test_teacher_renames_self(
    coordinator_client: TestClient, sent_mails: list[AccountMail]
) -> None:
    coordinator_client.post("/api/v1/users/", json={"email": "t1@example.com", "teacher_name": "王老師"})
    teacher = _login_client(coordinator_client, "t1@example.com", _password(sent_mails[0]))

    response = teacher.patch(ME_URL, json={"name": "王大明"})

    assert response.status_code == 200
    assert response.json()["name"] == "王大明"
    assert response.json()["role"] == "TEACHER"


def test_blank_name_returns_422(
    coordinator_client: TestClient, sent_mails: list[AccountMail]
) -> None:
    coordinator_client.post("/api/v1/users/", json={"email": "t1@example.com", "teacher_name": "王老師"})
    teacher = _login_client(coordinator_client, "t1@example.com", _password(sent_mails[0]))

    response = teacher.patch(ME_URL, json={"name": "  "})

    assert response.status_code == 422


def test_unassigned_teacher_cannot_rename(
    coordinator_client: TestClient, sent_mails: list[AccountMail]
) -> None:
    user = coordinator_client.post(
        "/api/v1/users/", json={"email": "t1@example.com", "teacher_name": "王老師"}
    ).json()["user"]
    coordinator_client.post(f"/api/v1/users/{user['id']}/leave-school")
    teacher = _login_client(coordinator_client, "t1@example.com", _password(sent_mails[0]))

    response = teacher.patch(ME_URL, json={"name": "王大明"})

    assert response.status_code == 422
    assert response.json()["detail"] == "目前無所屬學校，無法修改名字，請聯絡系統管理員"


def test_change_own_password(admin_client: TestClient) -> None:
    response = admin_client.patch(
        f"{ME_URL}/password",
        json={"current_password": "admin-test-password", "new_password": "brand-new-pass"},
    )

    assert response.status_code == 204
    login = admin_client.post(
        "/api/v1/auth/login", data={"username": "admin_test", "password": "brand-new-pass"}
    )
    assert login.status_code == 200


def test_wrong_current_password_returns_422(admin_client: TestClient) -> None:
    response = admin_client.patch(
        f"{ME_URL}/password",
        json={"current_password": "wrong-password", "new_password": "brand-new-pass"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "目前密碼不正確"


def test_new_password_follows_password_rule(admin_client: TestClient) -> None:
    response = admin_client.patch(
        f"{ME_URL}/password",
        json={"current_password": "admin-test-password", "new_password": "short"},
    )

    assert response.status_code == 422


def test_me_needs_login(unauthenticated_client: TestClient) -> None:
    assert unauthenticated_client.get(ME_URL).status_code == 401


def test_teacher_fixture_without_teacher_row(teacher_client: TestClient, db_session: Session, teacher_user: User) -> None:
    # An older account with no teacher row still has a profile (no name).
    response = teacher_client.get(ME_URL)

    assert response.status_code == 200
    assert response.json()["name"] is None
