from fastapi.testclient import TestClient

from app.models.user import User

# Task 59: account management endpoints. The `admin_client` fixture
# is the ADMIN (admin_user); `teacher_user` / `teacher_client` is a second,
# TEACHER account in the same database.


def _login(admin_client: TestClient, username: str, password: str) -> int:
    response = admin_client.post(
        "/api/v1/auth/login", data={"username": username, "password": password}
    )
    return response.status_code


# --- GET /api/v1/users ---


def test_list_users_as_admin(admin_client: TestClient, teacher_user: User) -> None:
    response = admin_client.get("/api/v1/users/")

    assert response.status_code == 200
    data = response.json()
    # 帳號改版: the 系統管理員 never sees 系統管理員 accounts, not even its own.
    assert [item["username"] for item in data] == ["teacher_test"]
    assert [item["role"] for item in data] == ["TEACHER"]
    for item in data:
        assert set(item.keys()) == {
            "id",
            "username",
            "role",
            "is_active",
            "school_id",
            "teacher_name",
            "teacher_id",
        }
        assert "hashed_password" not in item


def test_list_users_without_token_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.get("/api/v1/users/")

    assert response.status_code == 401


def test_list_users_as_teacher_returns_403(teacher_client: TestClient) -> None:
    response = teacher_client.get("/api/v1/users/")

    assert response.status_code == 403


# --- PATCH /api/v1/users/{id}/password ---


def test_reset_password_as_admin(admin_client: TestClient, teacher_user: User) -> None:
    response = admin_client.patch(
        f"/api/v1/users/{teacher_user.id}/password",
        json={"password": "brand-new-pass"},
    )

    assert response.status_code == 204
    assert _login(admin_client, "teacher_test", "brand-new-pass") == 200
    assert _login(admin_client, "teacher_test", "teacher-test-password") == 401


def test_reset_password_not_found(admin_client: TestClient) -> None:
    response = admin_client.patch(
        "/api/v1/users/999999/password", json={"password": "brand-new-pass"}
    )

    assert response.status_code == 404


def test_reset_password_as_teacher_returns_403(
    teacher_client: TestClient, teacher_user: User
) -> None:
    response = teacher_client.patch(
        f"/api/v1/users/{teacher_user.id}/password",
        json={"password": "brand-new-pass"},
    )

    assert response.status_code == 403


def test_reset_password_invalid_body_returns_422(
    admin_client: TestClient, teacher_user: User
) -> None:
    # Same rule as register's password field: a required string.
    missing_response = admin_client.patch(
        f"/api/v1/users/{teacher_user.id}/password", json={}
    )
    wrong_type_response = admin_client.patch(
        f"/api/v1/users/{teacher_user.id}/password", json={"password": 12345}
    )

    assert missing_response.status_code == 422
    assert wrong_type_response.status_code == 422
    # Neither rejected request may have changed the password.
    assert _login(admin_client, "teacher_test", "teacher-test-password") == 200


# --- 帳號改版: accounts are not deleted, they are 停用 ---


def test_delete_user_is_not_available(admin_client: TestClient, teacher_user: User) -> None:
    response = admin_client.delete(f"/api/v1/users/{teacher_user.id}")

    assert response.status_code == 405
    assert _login(admin_client, "teacher_test", "teacher-test-password") == 200


def test_deactivated_users_token_is_rejected(
    admin_client: TestClient, teacher_client: TestClient, teacher_user: User
) -> None:
    # The teacher's token works before the account is deactivated...
    assert teacher_client.get("/api/v1/schools/").status_code == 200

    response = admin_client.patch(f"/api/v1/users/{teacher_user.id}", json={"is_active": False})
    assert response.status_code == 200

    # ...and is rejected immediately afterwards, well before it expires:
    # get_current_user() looks the account up on every request.
    assert teacher_client.get("/api/v1/schools/").status_code == 401


# --- Task 59: password rule (8 characters to 72 UTF-8 bytes) ---

# Task 60: the exact Chinese messages backend/app/schemas/user.py raises
# (frontend/src/utils/passwordRule.ts uses the same text).
PASSWORD_TOO_SHORT_MESSAGE = "密碼至少需要 8 個字元"
PASSWORD_TOO_LONG_MESSAGE = "密碼太長，請縮短（中文等非英數字元每字會佔用較多長度）"


def _validation_messages(response_json: dict) -> list[str]:
    return [item["msg"] for item in response_json["detail"]]


def test_reset_password_too_short_rejected(
    admin_client: TestClient, teacher_user: User
) -> None:
    response = admin_client.patch(
        f"/api/v1/users/{teacher_user.id}/password", json={"password": "7chars!"}
    )

    assert response.status_code == 422
    assert any(
        PASSWORD_TOO_SHORT_MESSAGE in msg
        for msg in _validation_messages(response.json())
    )
    assert _login(admin_client, "teacher_test", "teacher-test-password") == 200


def test_reset_password_too_long_rejected(
    admin_client: TestClient, teacher_user: User
) -> None:
    response = admin_client.patch(
        f"/api/v1/users/{teacher_user.id}/password", json={"password": "a" * 73}
    )

    assert response.status_code == 422
    assert any(
        PASSWORD_TOO_LONG_MESSAGE in msg
        for msg in _validation_messages(response.json())
    )
    assert _login(admin_client, "teacher_test", "teacher-test-password") == 200


def test_reset_password_40_ascii_characters_accepted(
    admin_client: TestClient, teacher_user: User
) -> None:
    # Regression guard: a 40-character ASCII password is well inside the
    # rule (40 characters, 40 bytes) and must never be reported as too long.
    response = admin_client.patch(
        f"/api/v1/users/{teacher_user.id}/password", json={"password": "a" * 40}
    )

    assert response.status_code == 204
    assert _login(admin_client, "teacher_test", "a" * 40) == 200


def test_reset_password_over_72_bytes_rejected(
    admin_client: TestClient, teacher_user: User
) -> None:
    # 25 Chinese characters = 75 UTF-8 bytes: within 72 characters, but
    # over bcrypt's 72-byte input limit -- same rule as register.
    response = admin_client.patch(
        f"/api/v1/users/{teacher_user.id}/password", json={"password": "密" * 25}
    )

    assert response.status_code == 422
    assert any(
        PASSWORD_TOO_LONG_MESSAGE in msg
        for msg in _validation_messages(response.json())
    )
    assert _login(admin_client, "teacher_test", "teacher-test-password") == 200


def test_reset_password_exactly_8_characters_accepted(
    admin_client: TestClient, teacher_user: User
) -> None:
    response = admin_client.patch(
        f"/api/v1/users/{teacher_user.id}/password", json={"password": "8chars!!"}
    )

    assert response.status_code == 204
    assert _login(admin_client, "teacher_test", "8chars!!") == 200
