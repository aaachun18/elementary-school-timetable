from fastapi.testclient import TestClient


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


def test_register_duplicate_username_conflict(
    unauthenticated_client: TestClient,
) -> None:
    payload = {"username": "dupuser", "password": "s3cret-pass", "role": "TEACHER"}
    unauthenticated_client.post("/api/v1/auth/register", json=payload)

    response = unauthenticated_client.post("/api/v1/auth/register", json=payload)

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
        json={"username": "loginuser", "password": "correct-pass", "role": "TEACHER"},
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
        json={"username": "wrongpassuser", "password": "correct-pass", "role": "TEACHER"},
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
