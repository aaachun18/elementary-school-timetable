from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class InvalidTokenError(Exception):
    """Raised by decode_access_token() for any missing/expired/malformed/
    invalid-signature JWT, so callers don't need to know about python-jose's
    own exception types."""


def configure_bcrypt_rounds_for_testing(rounds: int) -> None:
    """Lower bcrypt's cost factor. Call this ONLY from the test suite's
    conftest.py -- never from application code. Production always runs with
    passlib's default (secure, deliberately slow) rounds; this exists
    purely so the test suite doesn't pay that cost on every fixture that
    creates a user, since tests don't need bcrypt's brute-force resistance.
    """
    _pwd_context.update(bcrypt__rounds=rounds)


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, get_settings().secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token, get_settings().secret_key, algorithms=[ALGORITHM]
        )
    except JWTError as exc:
        raise InvalidTokenError("Invalid or expired token") from exc
    return payload
