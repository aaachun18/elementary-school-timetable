"""移出課表 (POST /schedule-versions/{id}/unschedule-lesson): a lesson leaves
a manual edit's working copy and is unscheduled again -- with its whole
lesson block (連堂). Uses test_block_adjustment.py's world.
"""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from tests.conftest import mark_status_in_db
from tests.test_block_adjustment import URL, _check, _world
from tests.test_move_swap_lessons import _ok


def _unschedule(client: TestClient, version_id: int, schedule_id: int, *, dry_run: bool | None = None) -> Any:
    body: dict[str, Any] = {"schedule_id": schedule_id}
    if dry_run is not None:
        body["dry_run"] = dry_run
    return client.post(f"{URL}/{version_id}/unschedule-lesson", json=body)


def _unscheduled_lesson_ids(client: TestClient, version_id: int) -> set[int]:
    data = _ok(client.get(f"{URL}/{version_id}/unscheduled-lessons"))
    return {lesson["lesson_id"] for lesson in data["lessons"]}


def _row_exists(db: Session, schedule_id: int) -> bool:
    db.expire_all()
    return db.get(Schedule, schedule_id) is not None


def test_a_single_lesson_leaves_the_timetable(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    art = world.row("A1")

    data = _ok(_unschedule(client, world.version.id, art))

    assert data["changes"] == [
        {
            "schedule_id": art,
            "previous_time_slot_id": world.slot(1, 5),
            "new_time_slot_id": None,
            "previous_room_id": None,
            "new_room_id": None,
        }
    ]
    assert not _row_exists(db_session, art)
    assert _unscheduled_lesson_ids(client, world.version.id) == {world.lessons["A1"].id}
    # The lesson is missing from the week now: the check says so.
    assert "H7_WEEKLY_PERIODS" in {v["type"] for v in data["check"]["violations"]}
    assert data["check"]["violations"] == _check(client, world)["violations"]


def test_a_lesson_of_a_block_takes_its_whole_block(client: TestClient, db_session: Session) -> None:
    """Science 2+1: dragging S2 out removes block 1 (S1, S2); S3, the other
    block, stays."""
    world = _world(db_session)

    data = _ok(_unschedule(client, world.version.id, world.row("S2")))

    assert {change["schedule_id"] for change in data["changes"]} == {world.row("S1"), world.row("S2")}
    assert not _row_exists(db_session, world.row("S1"))
    assert not _row_exists(db_session, world.row("S2"))
    assert _row_exists(db_session, world.row("S3"))
    assert _unscheduled_lesson_ids(client, world.version.id) == {
        world.lessons["S1"].id,
        world.lessons["S2"].id,
    }


def test_dry_run_changes_nothing(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    data = _ok(_unschedule(client, world.version.id, world.row("M1"), dry_run=True))

    assert len(data["changes"]) == 2
    assert data["dry_run"] is True
    assert _row_exists(db_session, world.row("M1"))
    assert _row_exists(db_session, world.row("M2"))
    assert _unscheduled_lesson_ids(client, world.version.id) == set()


def test_only_a_working_copy_changes(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO")

    response = _unschedule(client, world.version.id, world.row("A1"))

    assert response.status_code == 409, response.json()
    assert _row_exists(db_session, world.row("A1"))


def test_an_unknown_lesson_row_is_404(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    response = _unschedule(client, world.version.id, 999999)

    assert response.status_code == 404, response.json()
    assert _unscheduled_lesson_ids(client, world.version.id) == set()


def test_an_unknown_record_is_404(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    response = _unschedule(client, 999999, world.row("A1"))

    assert response.status_code == 404


def test_a_teacher_cannot_unschedule(teacher_client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    response = _unschedule(teacher_client, world.version.id, world.row("A1"))

    assert response.status_code == 403
    assert _row_exists(db_session, world.row("A1"))


def test_an_unscheduled_lesson_can_be_placed_back(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    _ok(_unschedule(client, world.version.id, world.row("A1")))

    response = client.post(
        f"{URL}/{world.version.id}/place-lesson",
        json={"lesson_id": world.lessons["A1"].id, "time_slot_id": world.slot(3, 5), "teacher_id": world.t2.id},
    )

    assert response.status_code == 200, response.json()
    assert _unscheduled_lesson_ids(client, world.version.id) == set()
