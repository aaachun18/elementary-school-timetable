"""Task 94: a lesson whose requirement names a room type but whose row has
no room is reported as a WARNING (ROOM_MISSING_FOR_TYPE) -- H9 itself is
unchanged -- and the unscheduled-lessons list says which room placing
would use and whether any room of the type exists.

The timetable is test_block_adjustment.py's World (science 2+1, math 2,
english, art; no rooms), with science given a room type.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.grade_class import Class
from app.models.room import Room
from app.services.lesson_placement import default_room_id
from tests.test_block_adjustment import PLACEMENT, World, _check, _world
from tests.test_lesson_placement import _place, _place_candidates, _unscheduled
from tests.test_move_swap_lessons import _move, _ok, _swap

URL = "/api/v1/schedule-versions"
WARNING = "ROOM_MISSING_FOR_TYPE"


def _typed_world(db: Session, *, skip_rows: tuple[str, ...] = (), room_type: str = "自然教室") -> World:
    world = _world(db, skip_rows=skip_rows)
    world.science.required_room_type = room_type
    db.commit()
    return world


def _warnings(check: dict) -> list[dict]:
    return [v for v in check["violations"] if v["type"] == WARNING]


def _lesson(world: World, name: str) -> int:
    return world.lessons[name].id


# --- The warning ---


def test_each_lesson_without_a_room_gets_one_warning(client: TestClient, db_session: Session) -> None:
    world = _typed_world(db_session)

    check = _check(client, world)

    warnings = _warnings(check)
    assert [w["lesson_id"] for w in warnings] == [_lesson(world, n) for n in ("S1", "S2", "S3")]
    for name, warning in zip(("S1", "S2", "S3"), warnings):
        assert warning["severity"] == "WARNING"
        assert warning["schedule_id"] == world.row(name)
        assert warning["identity_key"] == f"{WARNING}:{_lesson(world, name)}"
        assert warning["class_subject_requirement_id"] == world.science.id
        assert warning["room_id"] is None
        assert warning["message"] == "四年甲班的自然指定了教室類型「自然教室」，但這堂課沒有教室（警告，不影響課表是否合法）"
        assert warning["suggested_action"]
    # Only warnings: the timetable stays valid (Task 88's rule).
    assert check["is_valid"] is True
    assert {v["type"] for v in check["violations"]} == {WARNING}


def test_no_warning_with_a_room_or_without_a_room_type(client: TestClient, db_session: Session) -> None:
    world = _typed_world(db_session)
    lab = Room(name="自然教室一", room_type="自然教室", is_active=True)
    db_session.add(lab)
    db_session.flush()
    for name in ("S1", "S2", "S3"):
        world.rows[name].room_id = lab.id
    db_session.commit()

    # Math, english and art have no room type and no room: nothing either.
    assert _check(client, world)["violations"] == []


def test_a_room_of_another_type_is_h9_not_this_warning(client: TestClient, db_session: Session) -> None:
    world = _typed_world(db_session)
    hall = Room(name="自然教室", room_type="專科教室", is_active=True)  # the name matches, the type doesn't
    db_session.add(hall)
    db_session.flush()
    world.rows["S1"].room_id = hall.id
    db_session.commit()

    check = _check(client, world)

    assert [v["lesson_id"] for v in check["violations"] if v["type"] == "H9_ROOM_TYPE"] == [_lesson(world, "S1")]
    assert [w["lesson_id"] for w in _warnings(check)] == [_lesson(world, n) for n in ("S2", "S3")]


def test_rows_without_teacher_or_time_slot_are_left_to_incomplete_row(
    client: TestClient, db_session: Session
) -> None:
    world = _typed_world(db_session)
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
    world = _typed_world(db_session)
    before = {w["identity_key"] for w in _warnings(_check(client, world))}

    preview = _ok(_move(client, world.version.id, world.row("S3"), world.slot(3, 5), dry_run=True))

    assert {w["identity_key"] for w in _warnings(preview["check"])} == before
    assert preview["check"]["is_valid"] is True


# --- Nothing is blocked ---


def test_moves_swaps_reassign_and_publish_are_not_blocked(client: TestClient, db_session: Session) -> None:
    world = _typed_world(db_session)

    moved = _ok(_move(client, world.version.id, world.row("S3"), world.slot(3, 5)))
    swapped = _ok(_swap(client, world.version.id, world.row("E1"), world.row("A1")))
    reassigned = _ok(client.post(
        f"{URL}/{world.version.id}/reassign-teacher",
        json={"class_subject_requirement_id": world.science.id, "new_teacher_id": world.t3.id},
    ))
    for data in (moved, swapped, reassigned):
        assert len(_warnings(data["check"])) == 3
        assert data["check"]["is_valid"] is True
    published = client.patch(f"{URL}/{world.version.id}", json={"status": "PUBLISHED"})
    assert published.status_code == 200, published.json()
    assert published.json()["status"] == "PUBLISHED"


def test_placing_without_a_room_is_warned_in_candidates_preview_and_check(
    client: TestClient, db_session: Session
) -> None:
    world = _typed_world(db_session, skip_rows=("S3",))
    lesson_id = _lesson(world, "S3")
    slot = world.slot(3, 5)

    candidates = _ok(_place_candidates(client, world.version.id, lesson_id, teacher_id=world.t1.id))
    preview = _ok(_place(client, world.version.id, lesson_id, slot, teacher_id=world.t1.id, dry_run=True))
    saved = _ok(_place(client, world.version.id, lesson_id, slot, teacher_id=world.t1.id))

    candidate = next(c for c in candidates["candidates"] if c["time_slot_id"] == slot)
    assert candidate["check"] == preview["check"]
    new = [w for w in _warnings(preview["check"]) if w["lesson_id"] == lesson_id]
    assert len(new) == 1 and new[0]["schedule_id"] is None  # no row yet in a preview
    assert preview["check"]["is_valid"] is True
    after = _check(client, world)
    assert saved["check"] == after
    row = next(w for w in _warnings(after) if w["lesson_id"] == lesson_id)
    assert row["schedule_id"] == saved["changes"][0]["schedule_id"]


# --- unscheduled-lessons: room_type, default_room_id, has_matching_room ---


def _science_and_art(client: TestClient, world: World) -> tuple[dict, dict]:
    lessons = {item["lesson_id"]: item for item in _ok(_unscheduled(client, world.version.id))["lessons"]}
    return lessons[_lesson(world, "S3")], lessons[_lesson(world, "A1")]


def _set_homeroom(db: Session, world: World, room: Room | None) -> None:
    class_ = db.get(Class, world.science.class_id)
    assert class_ is not None
    class_.homeroom_room_id = None if room is None else room.id
    db.commit()


@pytest.mark.parametrize(
    ("rooms", "expected"),
    [
        ([("自然教室一", "自然教室", True)], True),
        ([], False),
        ([("舊自然教室", "自然教室", False)], False),
        ([("自然教室", "專科教室", True)], False),  # a room NAMED like the type doesn't count
        ([("自然教室A", "自然教室 ", True)], False),  # nor a type with a trailing space
    ],
)
def test_room_type_fields_with_a_room_type(
    client: TestClient, db_session: Session, rooms: list[tuple[str, str, bool]], expected: bool
) -> None:
    world = _typed_world(db_session, skip_rows=("S3", "A1"))
    homeroom = Room(name="四甲教室", room_type="普通教室", is_active=True)
    db_session.add_all([homeroom, *(Room(name=n, room_type=t, is_active=a) for n, t, a in rooms)])
    db_session.flush()
    _set_homeroom(db_session, world, homeroom)

    science, _ = _science_and_art(client, world)

    assert science["room_type"] == "自然教室"
    assert science["has_matching_room"] is expected
    # A room type: placing picks nothing, the homeroom is never used.
    assert science["default_room_id"] is None
    assert (science["suggested_room_id"] is not None) is expected


@pytest.mark.parametrize("with_homeroom", [True, False])
def test_room_type_fields_without_a_room_type(
    client: TestClient, db_session: Session, with_homeroom: bool
) -> None:
    world = _typed_world(db_session, skip_rows=("S3", "A1"))
    homeroom = Room(name="四甲教室", room_type="普通教室", is_active=True)
    db_session.add(homeroom)
    db_session.flush()
    _set_homeroom(db_session, world, homeroom if with_homeroom else None)

    _, art = _science_and_art(client, world)

    expected_room = homeroom.id if with_homeroom else None
    assert (art["room_type"], art["has_matching_room"]) == (None, None)
    assert art["default_room_id"] == expected_room
    assert art["suggested_room_id"] == expected_room


def test_default_room_id_is_what_place_lesson_uses(client: TestClient, db_session: Session) -> None:
    world = _typed_world(db_session, skip_rows=("S3", "A1"))
    homeroom = Room(name="四甲教室", room_type="普通教室", is_active=True)
    db_session.add(homeroom)
    db_session.flush()
    _set_homeroom(db_session, world, homeroom)
    science, art = _science_and_art(client, world)

    placed_science = _ok(_place(client, world.version.id, science["lesson_id"], world.slot(3, 5), teacher_id=world.t1.id, dry_run=True))
    placed_art = _ok(_place(client, world.version.id, art["lesson_id"], world.slot(3, 6), teacher_id=world.t2.id, dry_run=True))

    assert placed_science["changes"][0]["new_room_id"] == science["default_room_id"] is None
    assert placed_art["changes"][0]["new_room_id"] == art["default_room_id"] == homeroom.id


def test_default_room_id_function() -> None:
    assert default_room_id(None, 5) == 5
    assert default_room_id(None, None) is None
    assert default_room_id("自然教室", 5) is None


def test_other_requirement_shapes_are_unchanged(client: TestClient, db_session: Session) -> None:
    """A version with nothing typed: no warning at all (as before)."""
    world = _world(db_session)

    assert _check(client, world)["violations"] == []
    assert len(PLACEMENT) == len(world.rows)
