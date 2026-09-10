import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# tests/conftest.py -> parent.parent is the repo root, which holds backend/
# (the `app` package). Mirrors the same bootstrap used in
# backend/alembic/env.py.
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(REPO_ROOT / ".env")

# Importing app.models registers every model's table on Base.metadata --
# without this, create_all()/drop_all() below would see an empty metadata
# (same pitfall as Task 2.5's alembic/env.py bug).
import app.models  # noqa: E402, F401
from app.core.security import (  # noqa: E402
    configure_bcrypt_rounds_for_testing,
    create_access_token,
    hash_password,
)
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402

# bcrypt is deliberately slow in production (that's the point). Nearly every
# test creates an admin/teacher user via the fixtures below, so at
# production cost the suite would pay that price ~100+ times over. Tests
# don't need brute-force resistance, so drop to bcrypt's minimum cost factor
# here -- this only ever touches the CryptContext instance inside this test
# process, never the deployed app.
configure_bcrypt_rounds_for_testing(4)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
DEV_DATABASE_URL = os.environ.get("DATABASE_URL")

if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set. Add it to your local .env -- see "
        "the TEST_DATABASE_URL example in .env.example. It must point at "
        "a separate database (e.g. timetable_test), not your dev database."
    )

if DEV_DATABASE_URL and TEST_DATABASE_URL == DEV_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL must not be the same as DATABASE_URL -- this "
        "test suite calls Base.metadata.drop_all() against it, which would "
        "destroy your dev database."
    )

test_engine = create_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """A clean database per test: create every table before the test runs,
    drop them all afterward, so no test can depend on data left behind by
    another one."""
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def admin_user(db_session: Session) -> User:
    user = User(
        username="admin_test",
        hashed_password=hash_password("admin-test-password"),
        role="ADMIN",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def teacher_user(db_session: Session) -> User:
    user = User(
        username="teacher_test",
        hashed_password=hash_password("teacher-test-password"),
        role="TEACHER",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user: User) -> str:
    return create_access_token({"sub": admin_user.username})


@pytest.fixture
def teacher_token(teacher_user: User) -> str:
    return create_access_token({"sub": teacher_user.username})


def _make_client(
    db_session: Session, token: str | None
) -> Generator[TestClient, None, None]:
    """Shared setup for every client-like fixture below: override get_db()
    to use the test database session, and attach a bearer token (or none)
    to every request the returned TestClient makes."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        yield TestClient(app, headers=headers)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(db_session: Session, admin_token: str) -> Generator[TestClient, None, None]:
    """Default TestClient used by nearly all existing tests. Carries a real,
    valid ADMIN JWT on every request (ADMIN satisfies both get_current_user
    and require_admin), so these tests exercise the real auth/RBAC
    dependencies rather than bypassing them -- no dependency_overrides for
    get_current_user/require_admin exist anywhere in this file."""
    yield from _make_client(db_session, admin_token)


@pytest.fixture
def teacher_client(
    db_session: Session, teacher_token: str
) -> Generator[TestClient, None, None]:
    """A TestClient authenticated as a TEACHER, for verifying the read-only
    side of RBAC (can GET, cannot POST/PATCH/DELETE)."""
    yield from _make_client(db_session, teacher_token)


@pytest.fixture
def unauthenticated_client(db_session: Session) -> Generator[TestClient, None, None]:
    """A TestClient with no Authorization header at all, for verifying that
    protected endpoints reject anonymous requests."""
    yield from _make_client(db_session, None)
