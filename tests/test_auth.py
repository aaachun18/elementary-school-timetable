from fastapi.testclient import TestClient

from app.models.user import User


def test_register_creates_user(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"username": "newadmin", "password": "s3cret-pass", "role": "ADMIN"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newadmin"
    assert data["role"] == "ADMIN"
    assert data["is_active"] is True
    assert "hashed_password" not in data
    assert "password" not in data


def test_register_duplicate_username_conflict(client: TestClient) -> None:
    # Task 57: once any user exists, register needs an ADMIN token -- the
    # `client` fixture's ADMIN, so the second call reaches the same
    # duplicate-username 409 as before.
    payload = {"username": "dupuser", "password": "s3cret-pass", "role": "TEACHER"}
    first_response = client.post("/api/v1/auth/register", json=payload)
    assert first_response.status_code == 201

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409


def test_register_invalid_role_returns_422(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"username": "studentuser", "password": "s3cret-pass", "role": "STUDENT"},
    )

    assert response.status_code == 422


def test_login_success(unauthenticated_client: TestClient) -> None:
    unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"username": "loginuser", "password": "correct-pass", "role": "ADMIN"},
    )

    response = unauthenticated_client.post(
        "/api/v1/auth/login",
        data={"username": "loginuser", "password": "correct-pass"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(unauthenticated_client: TestClient) -> None:
    unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"username": "wrongpassuser", "password": "correct-pass", "role": "ADMIN"},
    )

    response = unauthenticated_client.post(
        "/api/v1/auth/login",
        data={"username": "wrongpassuser", "password": "incorrect-pass"},
    )

    assert response.status_code == 401


def test_login_nonexistent_user(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/login",
        data={"username": "ghost", "password": "whatever"},
    )

    assert response.status_code == 401


def test_access_without_token_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.get("/api/v1/schools/")

    assert response.status_code == 401


def test_teacher_can_read(teacher_client: TestClient) -> None:
    response = teacher_client.get("/api/v1/schools/")

    assert response.status_code == 200


def test_teacher_cannot_write(teacher_client: TestClient) -> None:
    response = teacher_client.post("/api/v1/schools/", json={"name": "Nope School"})

    assert response.status_code == 403


# --- Task 57: register is anonymous only for the very first account ---


def test_register_first_user_is_always_admin(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"username": "firstuser", "password": "s3cret-pass", "role": "TEACHER"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "ADMIN"


def test_register_anonymous_rejected_when_users_exist(
    unauthenticated_client: TestClient, admin_user: User
) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"username": "sneaky", "password": "s3cret-pass", "role": "ADMIN"},
    )

    assert response.status_code == 401


def test_register_invalid_token_rejected_when_users_exist(
    unauthenticated_client: TestClient, admin_user: User
) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"username": "sneaky", "password": "s3cret-pass", "role": "ADMIN"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_register_teacher_token_forbidden(teacher_client: TestClient) -> None:
    response = teacher_client.post(
        "/api/v1/auth/register",
        json={"username": "sneaky", "password": "s3cret-pass", "role": "ADMIN"},
    )

    assert response.status_code == 403


def test_register_admin_creates_teacher(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "newteacher", "password": "s3cret-pass", "role": "TEACHER"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "TEACHER"


def test_register_admin_creates_admin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "secondadmin", "password": "s3cret-pass", "role": "ADMIN"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "ADMIN"


# --- Task 59: password rule (8 characters to 72 UTF-8 bytes) ---

# Task 60: the exact Chinese messages backend/app/schemas/user.py raises
# (frontend/src/utils/passwordRule.ts uses the same text).
PASSWORD_TOO_SHORT_MESSAGE = "密碼至少需要 8 個字元"
PASSWORD_TOO_LONG_MESSAGE = "密碼太長，請縮短（中文等非英數字元每字會佔用較多長度）"


def _validation_messages(response_json: dict) -> list[str]:
    return [item["msg"] for item in response_json["detail"]]


def test_register_password_too_short_rejected(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"username": "shortpw", "password": "7chars!", "role": "ADMIN"},
    )

    assert response.status_code == 422
    assert any(
        PASSWORD_TOO_SHORT_MESSAGE in msg
        for msg in _validation_messages(response.json())
    )


def test_register_password_too_long_rejected(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"username": "longpw", "password": "a" * 73, "role": "ADMIN"},
    )

    assert response.status_code == 422
    assert any(
        PASSWORD_TOO_LONG_MESSAGE in msg
        for msg in _validation_messages(response.json())
    )


def test_register_password_exactly_8_characters_accepted(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"username": "eightpw", "password": "8chars!!", "role": "ADMIN"},
    )

    assert response.status_code == 201


def test_register_password_40_ascii_characters_accepted(
    unauthenticated_client: TestClient,
) -> None:
    # Regression guard: a 40-character ASCII password is well inside the
    # rule (40 characters, 40 bytes) and must never be reported as too long.
    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"username": "fortypw", "password": "a" * 40, "role": "ADMIN"},
    )

    assert response.status_code == 201


def test_register_password_over_72_bytes_rejected(
    unauthenticated_client: TestClient,
) -> None:
    # 25 Chinese characters = 75 UTF-8 bytes: within 72 characters, but
    # over bcrypt's 72-byte input limit, so it must be rejected rather than
    # silently truncated.
    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"username": "bytespw", "password": "密" * 25, "role": "ADMIN"},
    )

    assert response.status_code == 422
    assert any(
        PASSWORD_TOO_LONG_MESSAGE in msg
        for msg in _validation_messages(response.json())
    )
