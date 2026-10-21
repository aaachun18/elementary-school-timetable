from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from tests.conftest import mark_status_in_db
from tests.test_requirement_edit_lock import _build_world, _set_status

# Task 73 / v3: ClassSubjectRequirementRead.is_locked -- computed per
# request: the requirement's record is no longer 尚未排課, the same rule the
# delete/update guards use. Response-only: never written from a request.

URL = "/api/v1/class-subject-requirements"


def _locked_in_list(client: TestClient, requirement_id: int) -> bool:
    response = client.get(f"{URL}/")
    assert response.status_code == 200
    (row,) = [item for item in response.json() if item["id"] == requirement_id]
    locked: bool = row["is_locked"]
    return locked


def _locked_single(client: TestClient, requirement_id: int) -> bool:
    response = client.get(f"{URL}/{requirement_id}")
    assert response.status_code == 200
    locked: bool = response.json()["is_locked"]
    return locked


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("NOT_SCHEDULED", False),
        ("AUTO", True),
        ("MANUAL", True),
        ("COPIED", True),
        ("EDITING", True),
    ],
)
def test_is_locked_follows_record_status(
    client: TestClient, db_session: Session, status: str, expected: bool
) -> None:
    world = _build_world(db_session)
    _set_status(db_session, world.version, status)

    assert _locked_in_list(client, world.requirement.id) is expected
    assert _locked_single(client, world.requirement.id) is expected


def test_unused_requirement_is_not_locked(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session, placed=False)

    assert _locked_in_list(client, world.requirement.id) is False
    assert _locked_single(client, world.requirement.id) is False


def test_is_locked_changes_with_the_record_status(
    client: TestClient, db_session: Session
) -> None:
    # Computed per request: it follows the record's current status.
    world = _build_world(db_session)
    assert _locked_single(client, world.requirement.id) is False

    _set_status(db_session, world.version, "AUTO")
    assert _locked_single(client, world.requirement.id) is True

    mark_status_in_db(db_session, world.version.id, "AUTO", is_published=True)
    assert _locked_single(client, world.requirement.id) is True


def test_list_and_single_agree_for_every_requirement(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    english, science = world.builder.subject("國語"), world.other_subject
    locked_version = world.builder.version(status="AUTO")
    world.builder.course(locked_version, world.other_class, english, world.other_teacher, [2])
    world.builder.course(world.version, world.other_class, science, world.other_teacher, [3])

    listed = {item["id"]: item["is_locked"] for item in client.get(f"{URL}/").json()}

    assert len(listed) == 3
    assert sorted(listed.values()) == [False, False, True]
    for requirement_id, is_locked in listed.items():
        assert _locked_single(client, requirement_id) is is_locked


def test_create_response_is_not_locked_and_ignores_is_locked_in_body(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session, placed=False)
    body = {
        "schedule_version_id": world.version.id,
        "class_id": world.other_class.id,
        "subject_id": world.other_subject.id,
        "weekly_periods": 2,
        "is_locked": True,
    }

    response = client.post(f"{URL}/", json=body)

    assert response.status_code == 201
    assert response.json()["is_locked"] is False


def test_patch_ignores_is_locked_in_body(client: TestClient, db_session: Session) -> None:
    # A 尚未排課 record's: not locked, and sending is_locked can't change that.
    world = _build_world(db_session)

    response = client.patch(
        f"{URL}/{world.requirement.id}", json={"is_locked": True, "weekly_periods": 3}
    )

    assert response.status_code == 200
    assert response.json()["is_locked"] is False
    assert response.json()["weekly_periods"] == 3
    assert _locked_single(client, world.requirement.id) is False
    assert not hasattr(ClassSubjectRequirement, "is_locked")


def test_teacher_sees_is_locked_too(teacher_client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO", is_published=True)

    assert _locked_in_list(teacher_client, world.requirement.id) is True


@contextmanager
def _count_statements(db: Session) -> Iterator[list[str]]:
    statements: list[str] = []
    engine = db.get_bind()

    def record(*args: Any) -> None:
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_list_is_locked_uses_one_query_regardless_of_size(
    client: TestClient, db_session: Session
) -> None:
    # No N+1: listing 1 requirement and listing 6 run the same number of
    # SQL statements.
    world = _build_world(db_session)
    with _count_statements(db_session) as one:
        assert client.get(f"{URL}/").status_code == 200

    for index in range(5):
        subject = world.builder.subject(f"科目{index}")
        world.builder.course(world.version, world.other_class, subject, world.other_teacher, [])
    with _count_statements(db_session) as six:
        response = client.get(f"{URL}/")
    assert len(response.json()) == 6

    assert len(six) == len(one)
