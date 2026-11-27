"""Task 94 / 98: a lesson whose requirement names a special room but whose
row has no room is reported as a WARNING (REQUIRED_ROOM_MISSING) -- H9
only compares a room that is there -- and the unscheduled-lessons list says
which room placing would use.

The timetable is test_block_adjustment.py's World (science 2+1, math 2,
english, art; rows written without rooms), with science given the required
room 自然教室一.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.room import Room
from app.services.lesson_placement import default_room_id
from tests.conftest import get_test_school_id
from tests.test_block_adjustment import PLACEMENT, World, _check, _world
from tests.test_lesson_placement import _place, _place_candidates, _unscheduled
from tests.test_move_swap_lessons import _move, _ok, _swap

URL = "/api/v1/schedule-versions"
WARNING = "REQUIRED_ROOM_MISSING"


def _room(db: Session, name: str, *, active: bool = True) -> Room:
    room = Room(school_id=get_test_school_id(db), name=name, is_active=active)
    db.add(room)
    db.flush()
    return room


def _lab_world(db: Session, *, skip_rows: tuple[str, ...] = ()) -> tuple[World, Room]:
    world = _world(db, skip_rows=skip_rows)
    lab = _room(db, "自然教室一")
    world.science.required_room_id = lab.id
    db.commit()
    return world, lab


def _warnings(check: dict) -> list[dict]:
    return [v for v in check["violations"] if v["type"] == WARNING]


def _lesson(world: World, name: str) -> int:
    return world.lessons[name].id


# --- The warning ---


def test_each_lesson_without_a_room_gets_one_warning(client: TestClient, db_session: Session) -> None:
    world, _ = _lab_world(db_session)

    check = _check(client, world)

    warnings = _warnings(check)
    assert [w["lesson_id"] for w in warnings] == [_lesson(world, n) for n in ("S1", "S2", "S3")]
    for name, warning in zip(("S1", "S2", "S3"), warnings):
        assert warning["severity"] == "WARNING"
        assert warning["schedule_id"] == world.row(name)
        assert warning["identity_key"] == f"{WARNING}:{_lesson(world, name)}"
        assert warning["class_subject_requirement_id"] == world.science.id
        assert warning["room_id"] is None
        assert warning["message"] == "四年甲班的自然指定在「自然教室一」上課，但這堂課沒有教室（警告，不影響課表是否合法）"
        assert warning["suggested_action"] == "把這堂課的教室設為「自然教室一」"
    # Only warnings: the timetable stays valid (Task 88's rule).
    assert check["is_valid"] is True
    assert {v["type"] for v in check["violations"]} == {WARNING}


def test_no_warning_in_the_required_room_or_without_one(client: TestClient, db_session: Session) -> None:
    world, lab = _lab_world(db_session)
    for name in ("S1", "S2", "S3"):
        world.rows[name].room_id = lab.id
    db_session.commit()

    # Math, english and art have no required room and no room: nothing either.
    assert _check(client, world)["violations"] == []


def test_another_room_is_h9_not_this_warning(client: TestClient, db_session: Session) -> None:
    world, _ = _lab_world(db_session)
    hall = _room(db_session, "禮堂")
    world.rows["S1"].room_id = hall.id
    db_session.commit()

    check = _check(client, world)

    assert [v["lesson_id"] for v in check["violations"] if v["type"] == "H9_REQUIRED_ROOM"] == [
        _lesson(world, "S1")
    ]
    assert [w["lesson_id"] for w in _warnings(check)] == [_lesson(world, n) for n in ("S2", "S3")]


def test_rows_without_teacher_or_time_slot_are_left_to_incomplete_row(
    client: TestClient, db_session: Session
) -> None:
    world, _ = _lab_world(db_session)
    world.rows["S1"].teacher_id = None
    world.rows["S3"].time_slot_id = None
    db_session.commit()

    check = _check(client, world)

    assert [w["lesson_id"] for w in _warnings(check)] == [_lesson(world, "S2")]
    assert {v["lesson_id"] for v in check["violations"] if v["type"] == "INCOMPLETE_SCHEDULE_ROW"} == {
        _lesson(world, "S1"),
        _lesson(world, "S3"),
    }


def test_the_warning_keeps_its_identity_when_the_lesson_moves(client: TestClient, db_session: Session) -> None:
    world, _ = _lab_world(db_session)
    before = {w["identity_key"] for w in _warnings(_check(client, world))}

    preview = _ok(_move(client, world.version.id, world.row("S3"), world.slot(3, 5), dry_run=True))

    assert {w["identity_key"] for w in _warnings(preview["check"])} == before
    assert preview["check"]["is_valid"] is True


# --- Nothing is blocked ---


def test_moves_swaps_reassign_and_publish_are_not_blocked(client: TestClient, db_session: Session) -> None:
    world, _ = _lab_world(db_session)

    moved = _ok(_move(client, world.version.id, world.row("S3"), world.slot(3, 5)))
    swapped = _ok(_swap(client, world.version.id, world.row("E1"), world.row("A1")))
    reassigned = _ok(client.post(
        f"{URL}/{world.version.id}/reassign-teacher",
        json={"class_subject_requirement_id": world.science.id, "new_teacher_id": world.t3.id},
    ))
    for data in (moved, swapped, reassigned):
        assert len(_warnings(data["check"])) == 3
        assert data["check"]["is_valid"] is True
    saved = _ok(client.post(f"{URL}/{world.version.id}/save"))
    published = client.post(f"{URL}/{saved['id']}/publish")
    assert published.status_code == 200, published.json()
    assert published.json()["is_published"] is True


def test_placing_uses_the_required_room_so_no_warning(
    client: TestClient, db_session: Session
) -> None:
    world, lab = _lab_world(db_session, skip_rows=("S3",))
    lesson_id = _lesson(world, "S3")
    slot = world.slot(3, 5)

    candidates = _ok(_place_candidates(client, world.version.id, lesson_id, teacher_id=world.t1.id))
    preview = _ok(_place(client, world.version.id, lesson_id, slot, teacher_id=world.t1.id, dry_run=True))
    saved = _ok(_place(client, world.version.id, lesson_id, slot, teacher_id=world.t1.id))

    candidate = next(c for c in candidates["candidates"] if c["time_slot_id"] == slot)
    assert candidate["check"] == preview["check"]
    assert preview["changes"][0]["new_room_id"] == lab.id
    assert [w for w in _warnings(preview["check"]) if w["lesson_id"] == lesson_id] == []
    after = _check(client, world)
    assert saved["check"] == after
    assert [w for w in _warnings(after) if w["lesson_id"] == lesson_id] == []


# --- unscheduled-lessons: required_room_id, default_room_id ---


def _science_and_art(client: TestClient, world: World) -> tuple[dict, dict]:
    lessons = {item["lesson_id"]: item for item in _ok(_unscheduled(client, world.version.id))["lessons"]}
    return lessons[_lesson(world, "S3")], lessons[_lesson(world, "A1")]


def test_required_room_is_the_default(client: TestClient, db_session: Session) -> None:
    world, lab = _lab_world(db_session, skip_rows=("S3", "A1"))

    science, _ = _science_and_art(client, world)

    assert science["required_room_id"] == lab.id
    assert science["default_room_id"] == science["suggested_room_id"] == lab.id


def test_without_a_required_room_there_is_no_room(
    client: TestClient, db_session: Session
) -> None:
    """原班上課: the class's own room is no school room."""
    world, _ = _lab_world(db_session, skip_rows=("S3", "A1"))
    _room(db_session, "四甲教室")  # a room nobody requires stays unused

    _, art = _science_and_art(client, world)

    assert art["required_room_id"] is None
    assert art["default_room_id"] is None
    assert art["suggested_room_id"] is None


def test_default_room_id_is_what_place_lesson_uses(client: TestClient, db_session: Session) -> None:
    world, lab = _lab_world(db_session, skip_rows=("S3", "A1"))
    science, art = _science_and_art(client, world)

    placed_science = _ok(_place(client, world.version.id, science["lesson_id"], world.slot(3, 5), teacher_id=world.t1.id, dry_run=True))
    placed_art = _ok(_place(client, world.version.id, art["lesson_id"], world.slot(3, 6), teacher_id=world.t2.id, dry_run=True))

    assert placed_science["changes"][0]["new_room_id"] == science["default_room_id"] == lab.id
    assert placed_art["changes"][0]["new_room_id"] == art["default_room_id"] is None


def test_default_room_id_function() -> None:
    assert default_room_id(None) is None
    assert default_room_id(7) == 7


def test_other_requirement_shapes_are_unchanged(client: TestClient, db_session: Session) -> None:
    """A version with no required room: no warning at all (as before)."""
    world = _world(db_session)

    assert _check(client, world)["violations"] == []
    assert len(PLACEMENT) == len(world.rows)
