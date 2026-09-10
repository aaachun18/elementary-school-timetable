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
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

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
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """A FastAPI TestClient whose get_db() dependency is overridden to use
    the test database session above, instead of the real dev database."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
