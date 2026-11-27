from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    IDLE_TIMEOUT_MINUTES,
    create_access_token,
    decode_access_token,
)
from app.models.user import User

# Idle logout (閒置自動登出): POST /api/v1/auth/refresh renews the token of
# someone still working, so only someone idle for IDLE_TIMEOUT_MINUTES is
# logged out -- not everyone a fixed time after logging in.

URL = "/api/v1/auth/refresh"


def test_a_token_outlives_the_idle_limit() -> None:
    assert IDLE_TIMEOUT_MINUTES == 30
    assert ACCESS_TOKEN_EXPIRE_MINUTES > IDLE_TIMEOUT_MINUTES


def test_refresh_returns_a_new_token_for_the_same_account(
    client: TestClient, coordinator_token: str
) -> None:
    response = client.post(URL)

    assert response.status_code == 200, response.json()
    payload = decode_access_token(response.json()["access_token"])
    assert payload["sub"] == decode_access_token(coordinator_token)["sub"]
    assert payload["role"] == "COORDINATOR"
    expires_in = datetime.fromtimestamp(payload["exp"], timezone.utc) - datetime.now(timezone.utc)
    assert timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES - 1) < expires_in <= timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )


def test_the_new_token_works(client: TestClient, unauthenticated_client: TestClient) -> None:
    token = client.post(URL).json()["access_token"]

    response = unauthenticated_client.get(
        "/api/v1/subjects/", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200


def test_every_role_can_refresh(admin_client: TestClient, teacher_client: TestClient) -> None:
    assert admin_client.post(URL).status_code == 200
    assert teacher_client.post(URL).status_code == 200


def test_no_token_is_refused(unauthenticated_client: TestClient) -> None:
    assert unauthenticated_client.post(URL).status_code == 401


def test_an_expired_token_is_refused(unauthenticated_client: TestClient) -> None:
    expired = jwt.encode(
        {
            "sub": "coordinator",
            "role": "COORDINATOR",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        get_settings().secret_key,
        algorithm=ALGORITHM,
    )

    response = unauthenticated_client.post(URL, headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


def test_a_deactivated_account_is_refused(
    unauthenticated_client: TestClient, db_session: Session, coordinator_token: str
) -> None:
    username = decode_access_token(coordinator_token)["sub"]
    user = db_session.query(User).filter(User.username == username).one()
    user.is_active = False
    db_session.commit()

    response = unauthenticated_client.post(
        URL, headers={"Authorization": f"Bearer {coordinator_token}"}
    )

    assert response.status_code == 401


def test_the_role_comes_from_the_account_not_the_old_token(
    unauthenticated_client: TestClient, coordinator_token: str
) -> None:
    username = decode_access_token(coordinator_token)["sub"]
    forged = create_access_token({"sub": username, "role": "ADMIN"})

    response = unauthenticated_client.post(URL, headers={"Authorization": f"Bearer {forged}"})

    assert decode_access_token(response.json()["access_token"])["role"] == "COORDINATOR"
