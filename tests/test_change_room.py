"""Task 95: POST /schedule-versions/{id}/change-room -- change the room of
lessons already in a DRAFT version (decision 32).

The timetable is test_block_adjustment.py's World: science 2+1 (S1 Mon 1,
S2 Mon 2 one block; S3 Tue 1), math 2 (M1 Tue 5, M2 Tue 6), english E1 Wed 1,
E2 Wed 2, art A1 Mon 5; no rooms.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.room import Room
from app.models.schedule import Schedule
from app.services import room_change
from tests.test_block_adjustment import World, _check, _world
from tests.test_move_swap_lessons import _ok, _schedule_snapshot

URL = "/api/v1/schedule-versions"


def _change(
    client: TestClient,
    version_id: int,
    schedule_id: int,
    room_id: int | None,
    *,
    scope: str | None = None,
    dry_run: bool | None = None,
) -> Any:
    body: dict[str, Any] = {"schedule_id": schedule_id, "room_id": room_id}
    if scope is not None:
        body["scope"] = scope
    if dry_run is not None:
        body["dry_run"] = dry_run
    return client.post(f"{URL}/{version_id}/change-room", json=body)


def _room(db: Session, name: str = "自然教室一", room_type: str = "自然教室", active: bool = True) -> Room:
    room = Room(name=name, room_type=room_type, is_active=active)
    db.add(room)
    db.commit()
    return room


def _rooms(world: World) -> dict[str, int | None]:
    world.db.expire_all()
    return {name: world.db.get(Schedule, row.id).room_id for name, row in world.rows.items()}  # type: ignore[union-attr]


def _changed(data: dict) -> dict[int, int | None]:
    return {change["schedule_id"]: change["new_room_id"] for change in data["changes"]}


def _types(check: dict) -> set[str]:
    return {violation["type"] for violation in check["violations"]}


# --- Which rows change ---


def test_single_lesson_changes_only_its_room(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    room = _room(db_session, "美勞教室", "美勞教室")

    data = _ok(_change(client, world.version.id, world.row("A1"), room.id))

    [change] = data["changes"]
    assert change == {
        "schedule_id": world.row("A1"),
        "lesson_id": world.lessons["A1"].id,
        "teacher_id": world.t2.id,
        "previous_time_slot_id": world.slot(1, 5),
        "new_time_slot_id": world.slot(1, 5),
        "previous_room_id": None,
        "new_room_id": room.id,
    }
    assert data["scope"] == "lesson" and data["dry_run"] is False
    rooms = _rooms(world)
    assert rooms["A1"] == room.id
    assert {name: r for name, r in rooms.items() if name != "A1"} == {name: None for name in rooms if name != "A1"}
    assert data["check"] == _check(client, world)


@pytest.mark.parametrize("picked", ["S1", "S2"])
def test_lesson_scope_takes_the_whole_block(client: TestClient, db_session: Session, picked: str) -> None:
    world = _world(db_session)
    room = _room(db_session)

    data = _ok(_change(client, world.version.id, world.row(picked), room.id))

    assert _changed(data) == {world.row("S1"): room.id, world.row("S2"): room.id}
    rooms = _rooms(world)
    assert (rooms["S1"], rooms["S2"], rooms["S3"]) == (room.id, room.id, None)


def test_the_one_lesson_block_of_2_plus_1_changes_alone(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    room = _room(db_session)

    data = _ok(_change(client, world.version.id, world.row("S3"), room.id))

    assert _changed(data) == {world.row("S3"): room.id}


def test_requirement_scope_changes_every_lesson_of_the_requirement(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    room = _room(db_session)

    data = _ok(_change(client, world.version.id, world.row("S3"), room.id, scope="requirement"))

    assert _changed(data) == {world.row(n): room.id for n in ("S1", "S2", "S3")}
    assert data["scope"] == "requirement"
    assert _rooms(world)["M1"] is None


def test_teacher_and_time_slot_never_change(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    room = _room(db_session)
    before = {r.id: (r.teacher_id, r.time_slot_id) for r in world.rows.values()}

    _ok(_change(client, world.version.id, world.row("S1"), room.id, scope="requirement"))

    world.db.expire_all()
    after = {r.id: (world.db.get(Schedule, r.id).teacher_id, world.db.get(Schedule, r.id).time_slot_id) for r in world.rows.values()}  # type: ignore[union-attr]
    assert after == before


def test_clearing_the_room(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    room = _room(db_session)
    _ok(_change(client, world.version.id, world.row("S1"), room.id))

    data = _ok(_change(client, world.version.id, world.row("S2"), None))

    assert _changed(data) == {world.row("S1"): None, world.row("S2"): None}
    assert (_rooms(world)["S1"], _rooms(world)["S2"]) == (None, None)


def test_the_same_room_is_a_200_with_no_changes(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    before = _schedule_snapshot(db_session)

    data = _ok(_change(client, world.version.id, world.row("A1"), None))

    assert data["changes"] == []
    assert data["check"] == _check(client, world)
    assert _schedule_snapshot(db_session) == before


def test_rows_already_in_the_room_are_not_listed(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    room = _room(db_session)
    _ok(_change(client, world.version.id, world.row("S3"), room.id))

    data = _ok(_change(client, world.version.id, world.row("S3"), room.id, scope="requirement"))

    assert _changed(data) == {world.row("S1"): room.id, world.row("S2"): room.id}


# --- Refusals (nothing changes) ---


def test_inactive_room_is_refused(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    room = _room(db_session, active=False)
    before = _schedule_snapshot(db_session)

    response = _change(client, world.version.id, world.row("A1"), room.id)

    assert (response.status_code, response.json()) == (409, {"detail": "無法指派已停用的教室"})
    assert _schedule_snapshot(db_session) == before


@pytest.mark.parametrize(("what", "detail"), [("room", "Room not found"), ("schedule", "Schedule not found")])
def test_missing_room_or_row_returns_404(client: TestClient, db_session: Session, what: str, detail: str) -> None:
    world = _world(db_session)

    response = (
        _change(client, world.version.id, world.row("A1"), 999999)
        if what == "room"
        else _change(client, world.version.id, 999999, None)
    )

    assert (response.status_code, response.json()["detail"]) == (404, detail)


def test_missing_version_returns_404(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    response = _change(client, 999999, world.row("A1"), None)

    assert (response.status_code, response.json()["detail"]) == (404, "ScheduleVersion not found")


@pytest.mark.parametrize(
    ("status", "detail"),
    [("PUBLISHED", "已發布版本不可修改，請建立新草稿版本"), ("ARCHIVED", "已封存的課表無法修改，請先複製成新草稿")],
)
def test_locked_version_returns_409(client: TestClient, db_session: Session, status: str, detail: str) -> None:
    world = _world(db_session)
    room = _room(db_session)
    world.version.status = status
    db_session.commit()
    before = _schedule_snapshot(db_session)

    response = _change(client, world.version.id, world.row("A1"), room.id)

    assert (response.status_code, response.json()) == (409, {"detail": detail})
    assert _schedule_snapshot(db_session) == before


def test_teacher_gets_403(teacher_client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    assert _change(teacher_client, world.version.id, world.row("A1"), None).status_code == 403


def test_bad_scope_is_422(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    assert _change(client, world.version.id, world.row("A1"), None, scope="class").status_code == 422


# --- Preview, check and atomicity ---


@pytest.mark.parametrize(("name", "scope"), [("A1", "lesson"), ("S2", "lesson"), ("S3", "requirement")])
def test_preview_matches_execution_and_check(
    client: TestClient, db_session: Session, name: str, scope: str
) -> None:
    world = _world(db_session)
    room = _room(db_session)
    before = _schedule_snapshot(db_session)

    preview = _ok(_change(client, world.version.id, world.row(name), room.id, scope=scope, dry_run=True))
    assert preview["dry_run"] is True
    assert _schedule_snapshot(db_session) == before
    saved = _ok(_change(client, world.version.id, world.row(name), room.id, scope=scope))

    assert preview["changes"] == saved["changes"]
    assert preview["check"] == saved["check"] == _check(client, world)


def test_failure_halfway_changes_nothing(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    world = _world(db_session)
    room = _room(db_session)
    before = _schedule_snapshot(db_session)
    real_apply = room_change._apply_room
    calls: list[int] = []

    def failing_apply(schedule: Schedule, room_id: int | None) -> Any:
        calls.append(schedule.id)
        if len(calls) == 2:
            raise RuntimeError("simulated failure on the second lesson")
        return real_apply(schedule, room_id)

    monkeypatch.setattr(room_change, "_apply_room", failing_apply)

    with pytest.raises(RuntimeError):
        room_change.change_room(db_session, world.version.id, world.row("S1"), room.id, "lesson", dry_run=False)

    assert len(calls) == 2
    assert _schedule_snapshot(db_session) == before


def test_a_room_of_another_type_is_reported_by_h9_not_refused(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.science.required_room_type = "自然教室"
    db_session.commit()
    hall = _room(db_session, "自然教室", "專科教室")  # named like the type, typed otherwise

    data = _ok(_change(client, world.version.id, world.row("S3"), hall.id))

    assert [v["lesson_id"] for v in data["check"]["violations"] if v["type"] == "H9_ROOM_TYPE"] == [world.lessons["S3"].id]


def test_giving_a_room_clears_the_missing_room_warning(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    world.science.required_room_type = "自然教室"
    db_session.commit()
    before = _check(client, world)
    assert [v["lesson_id"] for v in before["violations"] if v["type"] == "ROOM_MISSING_FOR_TYPE"] == [
        world.lessons[n].id for n in ("S1", "S2", "S3")
    ]
    lab = _room(db_session)  # created after scheduling

    data = _ok(_change(client, world.version.id, world.row("S1"), lab.id, scope="requirement"))

    assert data["check"]["violations"] == []
    assert _check(client, world)["violations"] == []


def test_a_room_already_used_then_is_a_new_room_conflict(client: TestClient, db_session: Session) -> None:
    """A1 is put in S1's slot (Mon 1) with the room by hand; giving S1
    the same room is an H3 room clash in the preview -- reported, not refused."""
    world = _world(db_session)
    room = _room(db_session)
    world.rows["A1"].time_slot_id = world.slot(1, 1)  # A1 now shares Mon 1 with S1 (H2 already)
    world.rows["A1"].room_id = room.id
    db_session.commit()
    assert "H3_ROOM_CONFLICT" not in _types(_check(client, world))

    preview = _ok(_change(client, world.version.id, world.row("S1"), room.id, dry_run=True))

    room_conflicts = [v for v in preview["check"]["violations"] if v["type"] == "H3_ROOM_CONFLICT"]
    assert {v["lesson_id"] for v in room_conflicts} == {world.lessons["S1"].id, world.lessons["A1"].id}
