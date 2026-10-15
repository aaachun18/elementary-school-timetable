from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from tests.test_reassign_teacher import World, _build_world, _reassign_ok

# Task 80: DELETE /api/v1/schedule-versions/{id} -- DRAFT and ARCHIVED
# versions can be deleted (together with their Schedule rows); the
# semester's PUBLISHED version cannot, it has to be unpublished first.
# A requirement's lock is computed from PUBLISHED/ARCHIVED Schedule rows at
# request time, so it follows deletions with nothing else to maintain.
# Test data is written straight to the database through db_session.

URL = "/api/v1/schedule-versions"
PUBLISHED_DELETE_MESSAGE = "已發布的版本無法刪除，請先取消發布"


# --- Helpers ---


def _set_status(client: TestClient, version_id: int, status: str) -> None:
    response = client.patch(f"{URL}/{version_id}", json={"status": status})
    assert response.status_code == 200, response.json()


def _copy(client: TestClient, version_id: int) -> int:
    response = client.post(f"{URL}/{version_id}/copy")
    assert response.status_code == 201, response.json()
    new_id: int = response.json()["id"]
    return new_id


def _delete(client: TestClient, version_id: int) -> Any:
    return client.delete(f"{URL}/{version_id}")


def _row_ids(db: Session, version_id: int) -> list[int]:
    db.expire_all()
    return list(
        db.scalars(
            select(Schedule.id)
            .where(Schedule.schedule_version_id == version_id)
            .order_by(Schedule.id)
        ).all()
    )


def _version_exists(db: Session, version_id: int) -> bool:
    db.expire_all()
    return db.get(ScheduleVersion, version_id) is not None


def _is_locked(client: TestClient, requirement_id: int) -> bool:
    response = client.get(f"/api/v1/class-subject-requirements/{requirement_id}")
    assert response.status_code == 200, response.json()
    locked: bool = response.json()["is_locked"]
    return locked


def _snapshot(db: Session) -> list[tuple[object, ...]]:
    """Every column of every version, requirement, Lesson and Schedule row."""
    db.expire_all()
    snapshot: list[tuple[object, ...]] = []
    for model in (ScheduleVersion, ClassSubjectRequirement, Lesson, Schedule):
        columns = list(model.__table__.columns.keys())
        for row in db.scalars(select(model).order_by(model.id)).all():
            snapshot.append((model.__name__, *(getattr(row, c) for c in columns)))
    return snapshot


def _archived_and_published(client: TestClient, db: Session) -> tuple[World, int]:
    """The world's v1 (with Schedule rows) copied to a second version, v1
    published, then the copy published -- so v1 is ARCHIVED and the copy,
    with the same rows, is PUBLISHED. Returns (world, copy id)."""
    world = _build_world(db)
    copy_id = _copy(client, world.version.id)
    _set_status(client, world.version.id, "PUBLISHED")
    _set_status(client, copy_id, "PUBLISHED")
    db.expire_all()
    assert db.get(ScheduleVersion, world.version.id).status == "ARCHIVED"  # type: ignore[union-attr]
    return world, copy_id


# --- ARCHIVED ---


def test_delete_archived_version_removes_it_and_its_rows_only(
    client: TestClient, db_session: Session
) -> None:
    world, copy_id = _archived_and_published(client, db_session)
    archived_rows = _row_ids(db_session, world.version.id)
    published_rows = _row_ids(db_session, copy_id)
    assert archived_rows and published_rows

    response = _delete(client, world.version.id)

    assert response.status_code == 204
    assert not _version_exists(db_session, world.version.id)
    assert _row_ids(db_session, world.version.id) == []
    remaining = set(db_session.scalars(select(Schedule.id)).all())
    assert remaining.isdisjoint(archived_rows)
    # The other version and its rows are untouched; Lessons and
    # requirements are version-independent and stay.
    assert _row_ids(db_session, copy_id) == published_rows
    assert client.get(f"{URL}/{copy_id}").json()["status"] == "PUBLISHED"
    assert client.get(
        f"/api/v1/class-subject-requirements/{world.english_requirement.id}"
    ).status_code == 200


def test_unpublish_then_delete_succeeds(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)
    _set_status(client, world.version.id, "PUBLISHED")
    _set_status(client, world.version.id, "ARCHIVED")

    response = _delete(client, world.version.id)

    assert response.status_code == 204
    assert not _version_exists(db_session, world.version.id)
    assert _row_ids(db_session, world.version.id) == []


# --- Requirement lock is recomputed ---


def test_deleting_the_only_locked_version_unlocks_the_requirement(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    requirement_id = world.english_requirement.id
    _set_status(client, world.version.id, "PUBLISHED")
    _set_status(client, world.version.id, "ARCHIVED")
    assert _is_locked(client, requirement_id) is True
    blocked = client.patch(
        f"/api/v1/class-subject-requirements/{requirement_id}", json={"consecutive_limit": 2}
    )
    assert blocked.status_code == 409

    assert _delete(client, world.version.id).status_code == 204

    assert _is_locked(client, requirement_id) is False
    edited = client.patch(
        f"/api/v1/class-subject-requirements/{requirement_id}", json={"consecutive_limit": 2}
    )
    assert edited.status_code == 200, edited.json()
    assert edited.json()["consecutive_limit"] == 2
    assert edited.json()["is_locked"] is False


def test_requirement_stays_locked_while_another_locked_version_uses_it(
    client: TestClient, db_session: Session
) -> None:
    world, _ = _archived_and_published(client, db_session)
    requirement_id = world.english_requirement.id

    assert _delete(client, world.version.id).status_code == 204

    # The PUBLISHED copy still has rows of this requirement.
    assert _is_locked(client, requirement_id) is True
    blocked = client.patch(
        f"/api/v1/class-subject-requirements/{requirement_id}", json={"consecutive_limit": 2}
    )
    assert blocked.status_code == 409


# --- PUBLISHED ---


def test_delete_published_version_returns_409_and_changes_nothing(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    _set_status(client, world.version.id, "PUBLISHED")
    before = _snapshot(db_session)

    response = _delete(client, world.version.id)

    assert response.status_code == 409
    assert response.json()["detail"] == PUBLISHED_DELETE_MESSAGE
    assert _snapshot(db_session) == before


# --- DRAFT (unchanged behaviour) ---


def test_delete_draft_version_removes_its_rows_and_leaves_other_versions(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    copy_id = _copy(client, world.version.id)
    copy_rows = _row_ids(db_session, copy_id)
    source_rows = _row_ids(db_session, world.version.id)

    response = _delete(client, copy_id)

    assert response.status_code == 204
    assert not _version_exists(db_session, copy_id)
    assert _row_ids(db_session, copy_id) == []
    assert copy_rows and set(db_session.scalars(select(Schedule.id)).all()).isdisjoint(copy_rows)
    assert _row_ids(db_session, world.version.id) == source_rows


# --- Copies keep no link to their source ---


def test_deleting_a_copy_source_leaves_the_copy_intact_and_usable(
    client: TestClient, db_session: Session
) -> None:
    # A copy records no "copied from" reference (schedules.schedule_version_id
    # is the only foreign key to schedule_versions), so deleting the source
    # cannot orphan or break the copy.
    world = _build_world(db_session)
    copy_id = _copy(client, world.version.id)
    copy_before = [
        (row.lesson_id, row.teacher_id, row.time_slot_id, row.room_id)
        for row in db_session.scalars(
            select(Schedule).where(Schedule.schedule_version_id == copy_id).order_by(Schedule.id)
        ).all()
    ]
    _set_status(client, world.version.id, "PUBLISHED")
    _set_status(client, world.version.id, "ARCHIVED")

    assert _delete(client, world.version.id).status_code == 204

    db_session.expire_all()
    copy_after = [
        (row.lesson_id, row.teacher_id, row.time_slot_id, row.room_id)
        for row in db_session.scalars(
            select(Schedule).where(Schedule.schedule_version_id == copy_id).order_by(Schedule.id)
        ).all()
    ]
    assert copy_after == copy_before
    assert client.get(f"{URL}/{copy_id}/check").status_code == 200
    second_copy = _copy(client, copy_id)
    assert len(_row_ids(db_session, second_copy)) == len(copy_before)


# --- Permissions / not found ---


def test_teacher_cannot_delete_any_version(
    teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    archived = world.builder.version(number=2)
    archived.status = "ARCHIVED"
    db_session.commit()

    for version_id in (world.version.id, archived.id):
        response = teacher_client.delete(f"{URL}/{version_id}")
        assert response.status_code == 403
        assert _version_exists(db_session, version_id)


def test_delete_missing_version_returns_404(client: TestClient) -> None:
    response = _delete(client, 999_999)

    assert response.status_code == 404


# --- Regression: other features keep working after a delete ---


def test_reassign_and_copy_still_work_after_deleting_an_archived_version(
    client: TestClient, db_session: Session
) -> None:
    world, published_id = _archived_and_published(client, db_session)
    assert _delete(client, world.version.id).status_code == 204

    draft_id = _copy(client, published_id)
    data = _reassign_ok(
        client, draft_id, world.science_requirement.id, world.old_teacher.id
    )

    assert data["updated_schedule_row_count"] == 1
    db_session.expire_all()
    teachers = {
        row.teacher_id
        for row in db_session.scalars(
            select(Schedule)
            .join(Lesson, Schedule.lesson_id == Lesson.id)
            .where(
                Schedule.schedule_version_id == draft_id,
                Lesson.class_subject_requirement_id == world.science_requirement.id,
            )
        ).all()
    }
    assert teachers == {world.old_teacher.id}
