"""Task 92: unscheduled lessons of a ScheduleVersion -- the list, the
place-candidates and placing them with place-lesson (decision 28).

The timetable is test_block_adjustment.py's World, built without the rows
named in skip_rows -- those lessons exist but are not in the version.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic_year import Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.teacher import Teacher, TeacherSubject
from app.services import lesson_placement
from tests.test_block_adjustment import PLACEMENT, World, _check, _refused, _world
from tests.test_move_swap_lessons import _ok, _schedule_snapshot

URL = "/api/v1/schedule-versions"


def _unscheduled(client: TestClient, version_id: int) -> Any:
    return client.get(f"{URL}/{version_id}/unscheduled-lessons")


def _place_candidates(
    client: TestClient, version_id: int, lesson_id: int, **params: int
) -> Any:
    return client.get(f"{URL}/{version_id}/place-candidates/{lesson_id}", params=params)


def _place(
    client: TestClient,
    version_id: int,
    lesson_id: int,
    time_slot_id: int,
    *,
    teacher_id: int | None = None,
    room_id: int | None = None,
    dry_run: bool | None = None,
) -> Any:
    body: dict[str, Any] = {"lesson_id": lesson_id, "time_slot_id": time_slot_id}
    if teacher_id is not None:
        body["teacher_id"] = teacher_id
    if room_id is not None:
        body["room_id"] = room_id
    if dry_run is not None:
        body["dry_run"] = dry_run
    return client.post(f"{URL}/{version_id}/place-lesson", json=body)


def _lesson(world: World, name: str) -> int:
    return world.lessons[name].id


def _placed(data: dict) -> dict[int, int]:
    """lesson_id -> new time slot of every change."""
    return {change["lesson_id"]: change["new_time_slot_id"] for change in data["changes"]}


def _types(check: dict) -> set[str]:
    return {violation["type"] for violation in check["violations"]}


def _rows_of(world: World) -> dict[int, Schedule]:
    """lesson_id -> the version's row, as stored now."""
    world.db.expire_all()
    rows = world.db.scalars(
        select(Schedule).where(Schedule.schedule_version_id == world.version.id)
    ).all()
    return {row.lesson_id: row for row in rows}


def _without_ids(check: dict, lesson_ids: set[int]) -> dict:
    """The check with schedule_id dropped for the placed lessons -- the one
    field a preview can't know (decision 28)."""
    return {
        **check,
        "violations": [
            {**v, "schedule_id": None} if v["lesson_id"] in lesson_ids else v
            for v in check["violations"]
        ],
    }


def _changes_without_ids(data: dict) -> list[dict]:
    return [{**change, "schedule_id": None} for change in data["changes"]]


# --- GET unscheduled-lessons ---


def test_fully_scheduled_version_lists_nothing_and_checks_as_before(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)

    data = _ok(_unscheduled(client, world.version.id))

    assert data == {"schedule_version_id": world.version.id, "lessons": []}
    assert _check(client, world)["violations"] == []


def test_partly_scheduled_version_lists_the_missing_lessons_in_order(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("A1", "S3", "S1"))

    lessons = _ok(_unscheduled(client, world.version.id))["lessons"]

    assert [item["lesson_id"] for item in lessons] == [
        _lesson(world, "S1"), _lesson(world, "S3"), _lesson(world, "A1"),
    ]
    first = lessons[0]
    assert (first["block_no"], first["block_seq"], first["lesson_pattern"]) == (1, 1, "2+1")
    assert (first["class_subject_requirement_id"], first["class_name"], first["subject_name"]) == (
        world.science.id, "四年甲班", "自然",
    )
    assert first["sequence_number"] == 1
    assert first["required_teacher_id"] is None
    assert first["suggested_room_id"] is None
    assert first["fixed_time_slot_id"] is None
    assert (lessons[1]["block_no"], lessons[1]["block_seq"]) == (2, 1)
    assert (lessons[2]["block_no"], lessons[2]["block_seq"], lessons[2]["lesson_pattern"]) == (None, None, None)


def test_unscheduled_version_lists_every_lesson(client: TestClient, db_session: Session) -> None:
    world = _world(db_session, skip_rows=tuple(PLACEMENT))

    lessons = _ok(_unscheduled(client, world.version.id))["lessons"]

    # Class, subject (自然, 數學, 英文, 美勞 by id), block, place in block.
    assert [item["lesson_id"] for item in lessons] == [
        _lesson(world, name) for name in ("S1", "S2", "S3", "M1", "M2", "E1", "E2", "A1")
    ]


def test_eligible_teachers_are_active_qualified_teachers_by_name(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("S1", "A1"))
    world.t1.name, world.t3.name = "B 老師", "A 老師"
    retired = Teacher(name="0 老師", is_active=False, min_weekly_periods=0, max_weekly_periods=20)
    db_session.add(retired)
    db_session.flush()
    db_session.add(TeacherSubject(teacher_id=retired.id, subject_id=world.science.subject_id))
    world.science.required_teacher_id = world.t1.id
    db_session.commit()

    science, art = _ok(_unscheduled(client, world.version.id))["lessons"]

    assert science["required_teacher_id"] == world.t1.id
    # Still listed with a required teacher; the inactive one never is.
    assert science["eligible_teachers"] == [
        {"teacher_id": world.t3.id, "name": "A 老師"},
        {"teacher_id": world.t1.id, "name": "B 老師"},
    ]
    assert art["eligible_teachers"] == [{"teacher_id": world.t2.id, "name": "二號老師"}]


def test_subject_nobody_can_teach_has_no_eligible_teachers(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("A1",))
    db_session.query(TeacherSubject).filter(TeacherSubject.teacher_id == world.t2.id).delete()
    db_session.commit()

    [art] = _ok(_unscheduled(client, world.version.id))["lessons"]

    assert art["eligible_teachers"] == []


def test_suggested_room_is_the_first_active_room_of_the_type(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("S3", "A1"))
    closed = Room(name="舊自然教室", room_type="自然教室", is_active=False)
    open_ = Room(name="自然教室一", room_type="自然教室", is_active=True)
    later = Room(name="自然教室二", room_type="自然教室", is_active=True)
    homeroom = Room(name="四甲教室", room_type="普通教室", is_active=True)
    db_session.add_all([closed, open_, later, homeroom])
    db_session.flush()
    world.science.required_room_type = "自然教室"
    db_session.get(Class, world.science.class_id).homeroom_room_id = homeroom.id  # type: ignore[union-attr]
    db_session.commit()

    science, art = _ok(_unscheduled(client, world.version.id))["lessons"]

    assert science["suggested_room_id"] == open_.id
    # Task 92B: no room type -> the class's homeroom.
    assert art["suggested_room_id"] == homeroom.id


def test_suggested_room_without_type_or_homeroom_is_none(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("A1",))

    [art] = _ok(_unscheduled(client, world.version.id))["lessons"]

    assert art["suggested_room_id"] is None


@pytest.mark.parametrize("status", ["PUBLISHED", "ARCHIVED"])
def test_list_is_readable_for_locked_versions(
    client: TestClient, db_session: Session, status: str
) -> None:
    world = _world(db_session, skip_rows=("A1",))
    world.version.status = status
    db_session.commit()

    lessons = _ok(_unscheduled(client, world.version.id))["lessons"]

    assert [item["lesson_id"] for item in lessons] == [_lesson(world, "A1")]


def test_lessons_of_other_semesters_are_not_listed(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    other = Semester(academic_year_id=world.version.semester.academic_year_id, number=2, is_active=False)
    db_session.add(other)
    db_session.flush()
    requirement = ClassSubjectRequirement(
        semester_id=other.id, class_id=world.science.class_id, subject_id=world.science.subject_id, weekly_periods=1
    )
    db_session.add(requirement)
    db_session.flush()
    db_session.add(Lesson(class_subject_requirement_id=requirement.id, sequence_number=1))
    db_session.commit()

    assert _ok(_unscheduled(client, world.version.id))["lessons"] == []


# --- place-lesson: single lessons ---


def test_place_single_lesson(client: TestClient, db_session: Session) -> None:
    world = _world(db_session, skip_rows=("A1",))
    assert _types(_check(client, world)) == {"H7_WEEKLY_PERIODS"}

    data = _ok(_place(client, world.version.id, _lesson(world, "A1"), world.slot(3, 5), teacher_id=world.t2.id))

    [change] = data["changes"]
    row = _rows_of(world)[_lesson(world, "A1")]
    assert change == {
        "schedule_id": row.id,
        "lesson_id": _lesson(world, "A1"),
        "teacher_id": world.t2.id,
        "previous_time_slot_id": None,
        "new_time_slot_id": world.slot(3, 5),
        "previous_room_id": None,
        "new_room_id": None,
    }
    assert (row.teacher_id, row.time_slot_id, row.room_id) == (world.t2.id, world.slot(3, 5), None)
    assert data["dry_run"] is False
    assert data["check"]["violations"] == []
    assert data["check"] == _check(client, world)


def test_dry_run_writes_nothing(client: TestClient, db_session: Session) -> None:
    world = _world(db_session, skip_rows=("A1",))
    before = _schedule_snapshot(db_session)

    data = _ok(_place(client, world.version.id, _lesson(world, "A1"), world.slot(3, 5), teacher_id=world.t2.id, dry_run=True))

    assert data["dry_run"] is True
    assert [change["schedule_id"] for change in data["changes"]] == [None]
    assert data["check"]["violations"] == []
    assert _schedule_snapshot(db_session) == before
    assert _types(_check(client, world)) == {"H7_WEEKLY_PERIODS"}


# --- place-lesson: lesson blocks ---


@pytest.mark.parametrize(("dragged", "target"), [("S1", (3, 5)), ("S2", (3, 6))])
def test_place_block_starts_k_minus_1_periods_before_the_target(
    client: TestClient, db_session: Session, dragged: str, target: tuple[int, int]
) -> None:
    world = _world(db_session, skip_rows=("S1", "S2"))

    data = _ok(_place(client, world.version.id, _lesson(world, dragged), world.slot(*target), teacher_id=world.t1.id))

    expected = {_lesson(world, "S1"): world.slot(3, 5), _lesson(world, "S2"): world.slot(3, 6)}
    assert _placed(data) == expected
    assert [change["lesson_id"] for change in data["changes"]] == list(expected)  # block order
    rows = _rows_of(world)
    assert {rows[lesson_id].time_slot_id for lesson_id in expected} == set(expected.values())
    assert {rows[lesson_id].teacher_id for lesson_id in expected} == {world.t1.id}
    assert data["check"]["violations"] == []


def test_partly_placed_block_places_the_missing_lesson_next_to_it(
    client: TestClient, db_session: Session
) -> None:
    """S2 is in Mon 2: S1 can only go to Mon 1 (the block's own range)."""
    world = _world(db_session, skip_rows=("S1",))
    before = _schedule_snapshot(db_session)

    elsewhere = _place(client, world.version.id, _lesson(world, "S1"), world.slot(3, 5), teacher_id=world.t1.id)
    _refused(elsewhere, "BLOCK_PARTIAL_MISMATCH")
    assert _schedule_snapshot(db_session) == before

    data = _ok(_place(client, world.version.id, _lesson(world, "S1"), world.slot(1, 1), teacher_id=world.t1.id))

    assert _placed(data) == {_lesson(world, "S1"): world.slot(1, 1)}
    assert data["check"]["violations"] == []
    assert _rows_of(world)[_lesson(world, "S2")].time_slot_id == world.slot(1, 2)  # never moved


def test_partly_placed_block_with_a_row_without_time_slot_is_refused(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("S1",))
    world.rows["S2"].time_slot_id = None
    db_session.commit()

    _refused(
        _place(client, world.version.id, _lesson(world, "S1"), world.slot(1, 1), teacher_id=world.t1.id),
        "BLOCK_PARTIAL_MISMATCH",
    )


@pytest.mark.parametrize(
    ("skip", "name", "target", "teacher", "why"),
    [
        (("A1",), "A1", (1, 1), "t2", "a single lesson onto S1"),
        (("S1", "S2"), "S1", (3, 1), "t1", "the block onto E1 and E2"),
        (("S1", "S2"), "S2", (3, 3), "t1", "the block's first lesson onto E2"),
    ],
)
def test_target_occupied_by_the_class_is_refused(
    client: TestClient, db_session: Session, skip: tuple[str, ...], name: str, target: tuple[int, int], teacher: str, why: str
) -> None:
    world = _world(db_session, skip_rows=skip)
    before = _schedule_snapshot(db_session)

    response = _place(client, world.version.id, _lesson(world, name), world.slot(*target), teacher_id=getattr(world, teacher).id)

    _refused(response, "BLOCK_TARGET_OCCUPIED")
    assert response.json()["detail"] == "要放入的時段已有本班的其他課"
    assert _schedule_snapshot(db_session) == before, why


@pytest.mark.parametrize(
    ("name", "target", "reason", "why"),
    [
        ("S1", (1, 3), "BLOCK_OUT_OF_RANGE", "the second lesson would fall on lunch"),
        ("S2", (1, 1), "BLOCK_OUT_OF_RANGE", "the first lesson would need a period before period 1"),
        ("S1", (2, 6), "BLOCK_OUT_OF_RANGE", "the second lesson would be after the last period"),
        ("S2", (2, 5), "BLOCK_OUT_OF_RANGE", "the first lesson would fall on lunch (across lunch)"),
        ("S1", (1, 4), "NON_TEACHING_SLOT", "lunch itself"),
    ],
)
def test_block_out_of_range_and_across_lunch_is_refused(
    client: TestClient, db_session: Session, name: str, target: tuple[int, int], reason: str, why: str
) -> None:
    world = _world(db_session, skip_rows=("S1", "S2"))
    before = _schedule_snapshot(db_session)

    _refused(_place(client, world.version.id, _lesson(world, name), world.slot(*target), teacher_id=world.t1.id), reason)
    assert _schedule_snapshot(db_session) == before, why


def test_single_lesson_onto_non_teaching_slot_is_refused(client: TestClient, db_session: Session) -> None:
    world = _world(db_session, skip_rows=("A1",))

    response = _place(client, world.version.id, _lesson(world, "A1"), world.slot(2, 4), teacher_id=world.t2.id)

    _refused(response, "NON_TEACHING_SLOT")
    assert response.json()["detail"] == "目標時段不是上課時段"


# --- Teacher and room ---


def test_without_any_teacher_placing_and_candidates_are_refused(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("A1",))

    place = _place(client, world.version.id, _lesson(world, "A1"), world.slot(3, 5))
    candidates = _place_candidates(client, world.version.id, _lesson(world, "A1"))

    for response in (place, candidates):
        _refused(response, "TEACHER_REQUIRED")
        assert response.json()["detail"] == "這堂課的需求沒有指定教師，請先選擇教師"
    assert _lesson(world, "A1") not in _rows_of(world)


def test_required_teacher_is_used_when_the_request_has_none(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("A1",))
    requirement = db_session.get(ClassSubjectRequirement, world.lessons["A1"].class_subject_requirement_id)
    requirement.required_teacher_id = world.t2.id  # type: ignore[union-attr]
    db_session.commit()

    candidates = _ok(_place_candidates(client, world.version.id, _lesson(world, "A1")))
    data = _ok(_place(client, world.version.id, _lesson(world, "A1"), world.slot(3, 5)))

    assert candidates["teacher_id"] == world.t2.id
    assert data["changes"][0]["teacher_id"] == world.t2.id
    assert _rows_of(world)[_lesson(world, "A1")].teacher_id == world.t2.id
    assert data["check"]["violations"] == []


def test_request_teacher_wins_over_the_required_one_and_is_reported(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("A1",))
    requirement = db_session.get(ClassSubjectRequirement, world.lessons["A1"].class_subject_requirement_id)
    requirement.required_teacher_id = world.t2.id  # type: ignore[union-attr]
    db_session.commit()

    data = _ok(_place(client, world.version.id, _lesson(world, "A1"), world.slot(3, 5), teacher_id=world.t1.id))

    assert _rows_of(world)[_lesson(world, "A1")].teacher_id == world.t1.id
    # Not refused: the check reports both (t1 can't teach art, t2 is required).
    assert _types(data["check"]) == {"H5_TEACHER_QUALIFICATION", "H6_REQUIRED_TEACHER"}


def test_missing_or_inactive_teacher_is_refused(client: TestClient, db_session: Session) -> None:
    world = _world(db_session, skip_rows=("A1",))
    world.t3.is_active = False
    db_session.commit()

    missing = _place(client, world.version.id, _lesson(world, "A1"), world.slot(3, 5), teacher_id=999999)
    inactive = _place(client, world.version.id, _lesson(world, "A1"), world.slot(3, 5), teacher_id=world.t3.id)

    assert (missing.status_code, missing.json()["detail"]) == (404, "Teacher not found")
    assert (inactive.status_code, inactive.json()["detail"]) == (409, "無法指派已停用的老師")
    assert _lesson(world, "A1") not in _rows_of(world)


@pytest.mark.parametrize(
    ("name", "teacher", "homeroom", "named_room", "expected", "why"),
    [
        ("A1", "t2", True, False, "homeroom", "no room type, the class has a homeroom"),
        ("A1", "t2", False, False, None, "no room type, no homeroom: empty as before"),
        ("S3", "t1", True, False, None, "a room type: never the homeroom"),
        ("A1", "t2", True, True, "named", "the request's room wins"),
    ],
)
def test_room_default_follows_run_scheduler(
    client: TestClient,
    db_session: Session,
    name: str,
    teacher: str,
    homeroom: bool,
    named_room: bool,
    expected: str | None,
    why: str,
) -> None:
    """Task 92B (decision 29): the same room rule as run-scheduler."""
    world = _world(db_session, skip_rows=(name,))
    room = Room(name="四甲教室", room_type="普通教室", is_active=True)
    other = Room(name="美勞教室", room_type="美勞教室", is_active=True)
    db_session.add_all([room, other])
    db_session.flush()
    world.science.required_room_type = "自然教室"
    if homeroom:
        db_session.get(Class, world.science.class_id).homeroom_room_id = room.id  # type: ignore[union-attr]
    db_session.commit()
    room_id = other.id if named_room else None
    want = {"homeroom": room.id, "named": other.id, None: None}[expected]

    candidates = _ok(_place_candidates(
        client, world.version.id, _lesson(world, name), teacher_id=getattr(world, teacher).id,
        **({"room_id": room_id} if room_id is not None else {}),
    ))
    data = _ok(_place(client, world.version.id, _lesson(world, name), world.slot(3, 5), teacher_id=getattr(world, teacher).id, room_id=room_id))

    assert candidates["room_id"] == want, why
    assert data["changes"][0]["new_room_id"] == want, why
    assert _rows_of(world)[_lesson(world, name)].room_id == want, why


def test_room_type_requirement_is_checked_only_once_a_room_is_named(
    client: TestClient, db_session: Session
) -> None:
    """No room is picked for a room-type requirement. H9 compares a room
    that is there, so an empty room is not reported (as for any row, e.g.
    the science rows of this World) -- a room of another type is."""
    world = _world(db_session, skip_rows=("S3",))
    lab = Room(name="自然教室一", room_type="自然教室", is_active=True)
    hall = Room(name="禮堂", room_type="禮堂", is_active=True)
    db_session.add_all([lab, hall])
    world.science.required_room_type = "自然教室"
    db_session.commit()

    def h9(room_id: int | None) -> bool:
        data = _ok(_place(client, world.version.id, _lesson(world, "S3"), world.slot(3, 5), teacher_id=world.t1.id, room_id=room_id, dry_run=True))
        assert data["changes"][0]["new_room_id"] == room_id
        return _lesson(world, "S3") in {v["lesson_id"] for v in data["check"]["violations"] if v["type"] == "H9_ROOM_TYPE"}

    assert (h9(None), h9(lab.id), h9(hall.id)) == (False, False, True)


def test_missing_room_or_time_slot_returns_404(client: TestClient, db_session: Session) -> None:
    world = _world(db_session, skip_rows=("A1",))

    room = _place(client, world.version.id, _lesson(world, "A1"), world.slot(3, 5), teacher_id=world.t2.id, room_id=999999)
    slot = _place(client, world.version.id, _lesson(world, "A1"), 999999, teacher_id=world.t2.id)

    assert (room.status_code, room.json()["detail"]) == (404, "Room not found")
    assert (slot.status_code, slot.json()["detail"]) == (404, "TimeSlot not found")


# --- Which lessons can be placed ---


def test_lesson_of_another_semester_is_refused(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    other = Semester(academic_year_id=world.version.semester.academic_year_id, number=2, is_active=False)
    db_session.add(other)
    db_session.flush()
    requirement = ClassSubjectRequirement(
        semester_id=other.id, class_id=world.science.class_id, subject_id=world.science.subject_id, weekly_periods=1
    )
    db_session.add(requirement)
    db_session.flush()
    foreign = Lesson(class_subject_requirement_id=requirement.id, sequence_number=1)
    db_session.add(foreign)
    db_session.commit()

    place = _place(client, world.version.id, foreign.id, world.slot(3, 5), teacher_id=world.t1.id)
    candidates = _place_candidates(client, world.version.id, foreign.id, teacher_id=world.t1.id)

    for response in (place, candidates):
        assert (response.status_code, response.json()["detail"]) == (409, "此課程不屬於該課表的學期")


def test_lesson_already_in_the_version_is_refused(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    place = _place(client, world.version.id, _lesson(world, "A1"), world.slot(3, 5), teacher_id=world.t2.id)
    candidates = _place_candidates(client, world.version.id, _lesson(world, "A1"), teacher_id=world.t2.id)

    for response in (place, candidates):
        assert (response.status_code, response.json()["detail"]) == (409, "此課程在該課表已有排課紀錄，請改用移動")


def test_missing_lesson_returns_404(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    response = _place(client, world.version.id, 999999, world.slot(3, 5), teacher_id=world.t2.id)

    assert (response.status_code, response.json()["detail"]) == (404, "Lesson not found")
    assert _place_candidates(client, world.version.id, 999999, teacher_id=world.t2.id).status_code == 404


# --- Atomicity ---


def test_failure_halfway_through_a_block_writes_nothing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = _world(db_session, skip_rows=("S1", "S2"))
    before = _schedule_snapshot(db_session)
    real_new_row = lesson_placement._new_row
    calls: list[int] = []

    def failing_new_row(*args: Any) -> Schedule:
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("simulated failure on the second lesson")
        return real_new_row(*args)

    monkeypatch.setattr(lesson_placement, "_new_row", failing_new_row)

    with pytest.raises(RuntimeError):
        lesson_placement.place_lesson(
            db_session, world.version.id, _lesson(world, "S1"), world.slot(3, 5), world.t1.id, None, dry_run=False
        )

    assert len(calls) == 2
    assert _schedule_snapshot(db_session) == before


# --- Permissions and version status ---


def test_teacher_gets_403(teacher_client: TestClient, db_session: Session) -> None:
    world = _world(db_session, skip_rows=("A1",))
    world.version.status = "PUBLISHED"  # even a version a TEACHER may read
    db_session.commit()

    assert _unscheduled(teacher_client, world.version.id).status_code == 403
    assert _place_candidates(teacher_client, world.version.id, _lesson(world, "A1"), teacher_id=world.t2.id).status_code == 403
    assert _place(teacher_client, world.version.id, _lesson(world, "A1"), world.slot(3, 5), teacher_id=world.t2.id).status_code == 403


def test_missing_version_returns_404(client: TestClient, db_session: Session) -> None:
    world = _world(db_session, skip_rows=("A1",))

    for response in (
        _unscheduled(client, 999999),
        _place_candidates(client, 999999, _lesson(world, "A1"), teacher_id=world.t2.id),
        _place(client, 999999, _lesson(world, "A1"), world.slot(3, 5), teacher_id=world.t2.id),
    ):
        assert (response.status_code, response.json()["detail"]) == (404, "ScheduleVersion not found")


@pytest.mark.parametrize(
    ("status", "detail"),
    [
        ("PUBLISHED", "已發布版本不可修改，請建立新草稿版本"),
        ("ARCHIVED", "已封存的課表無法修改，請先複製成新草稿"),
    ],
)
def test_locked_version_returns_409_before_anything_else(
    client: TestClient, db_session: Session, status: str, detail: str
) -> None:
    world = _world(db_session, skip_rows=("A1",))
    world.version.status = status
    db_session.commit()
    before = _schedule_snapshot(db_session)

    # No teacher anywhere and lunch as target: the lock is reported first.
    place = _place(client, world.version.id, _lesson(world, "A1"), world.slot(1, 4))
    candidates = _place_candidates(client, world.version.id, _lesson(world, "A1"))

    for response in (place, candidates):
        assert response.status_code == 409
        assert response.json() == {"detail": detail}
    assert _schedule_snapshot(db_session) == before


# --- Consistency: preview = execution = /check = candidates ---


@pytest.mark.parametrize(
    ("skip", "name", "target", "teacher"),
    [
        (("A1",), "A1", (3, 5), "t2"),
        (("A1",), "A1", (3, 5), "t1"),  # t1 can't teach art: H5 on the new lesson
        (("S1", "S2"), "S2", (3, 6), "t1"),
        (("S1", "S2"), "S1", (2, 2), "t3"),  # science twice on Tuesday
        (("S1",), "S1", (1, 1), "t3"),
    ],
)
def test_preview_matches_execution_and_check(
    client: TestClient, db_session: Session, skip: tuple[str, ...], name: str, target: tuple[int, int], teacher: str
) -> None:
    world = _world(db_session, skip_rows=skip)
    teacher_id = getattr(world, teacher).id
    before = _check(client, world)

    preview = _ok(_place(client, world.version.id, _lesson(world, name), world.slot(*target), teacher_id=teacher_id, dry_run=True))
    assert _check(client, world) == before
    saved = _ok(_place(client, world.version.id, _lesson(world, name), world.slot(*target), teacher_id=teacher_id))

    placed = set(_placed(saved))
    assert _changes_without_ids(preview) == _changes_without_ids(saved)
    after = _check(client, world)
    assert saved["check"] == after
    assert preview["check"] == _without_ids(after, placed)
    # Only the placed lessons' violations lose their schedule_id.
    assert all(
        v["schedule_id"] is None for v in preview["check"]["violations"] if v["lesson_id"] in placed
    )


@pytest.mark.parametrize(
    ("skip", "name", "teacher"),
    [(("A1",), "A1", "t2"), (("S1", "S2"), "S2", "t1"), (("S1",), "S1", "t1"), (("S3",), "S3", "t3")],
)
def test_candidates_match_previews_for_every_slot(
    client: TestClient, db_session: Session, skip: tuple[str, ...], name: str, teacher: str
) -> None:
    world = _world(db_session, skip_rows=skip)
    teacher_id = getattr(world, teacher).id
    before = _check(client, world)
    compared = refused = 0

    data = _ok(_place_candidates(client, world.version.id, _lesson(world, name), teacher_id=teacher_id))

    assert data["baseline"] == before
    assert (data["lesson_id"], data["teacher_id"], data["room_id"]) == (_lesson(world, name), teacher_id, None)
    assert len(data["candidates"]) == len(world.slots)
    for candidate in data["candidates"]:
        slot_id = candidate["time_slot_id"]
        response = _place(client, world.version.id, _lesson(world, name), slot_id, teacher_id=teacher_id, dry_run=True)
        if candidate["available"]:
            preview = _ok(response)
            assert candidate["check"] == preview["check"], slot_id
            if candidate["block_members"] is not None:
                assert {m["lesson_id"]: m["to_time_slot_id"] for m in candidate["block_members"]} == _placed(preview)
            compared += 1
        else:
            assert candidate["check"] is None and candidate["block_members"] is None
            _refused(response, candidate["unavailable_reason"])
            refused += 1

    assert compared > 0 and refused > 0
    assert _check(client, world) == before  # every call was read-only


def test_candidate_block_members_only_for_lessons_in_a_block(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("S1", "S2", "A1"))

    block = {c["time_slot_id"]: c for c in _ok(_place_candidates(client, world.version.id, _lesson(world, "S2"), teacher_id=world.t1.id))["candidates"]}
    single = _ok(_place_candidates(client, world.version.id, _lesson(world, "A1"), teacher_id=world.t2.id))["candidates"]

    assert block[world.slot(3, 6)]["block_members"] == [
        {"lesson_id": _lesson(world, "S1"), "to_time_slot_id": world.slot(3, 5)},
        {"lesson_id": _lesson(world, "S2"), "to_time_slot_id": world.slot(3, 6)},
    ]
    assert block[world.slot(1, 1)]["unavailable_reason"] == "BLOCK_OUT_OF_RANGE"
    assert block[world.slot(1, 4)]["unavailable_reason"] == "NON_TEACHING_SLOT"
    assert all(c["block_members"] is None for c in single)


def test_room_parameter_is_used_by_candidates(client: TestClient, db_session: Session) -> None:
    world = _world(db_session, skip_rows=("A1",))
    room = Room(name="美勞教室", room_type="美勞教室", is_active=True)
    db_session.add(room)
    db_session.commit()

    data = _ok(_place_candidates(client, world.version.id, _lesson(world, "A1"), teacher_id=world.t2.id, room_id=room.id))
    preview = _ok(_place(client, world.version.id, _lesson(world, "A1"), world.slot(3, 5), teacher_id=world.t2.id, room_id=room.id, dry_run=True))

    assert data["room_id"] == room.id
    candidate = next(c for c in data["candidates"] if c["time_slot_id"] == world.slot(3, 5))
    assert candidate["check"] == preview["check"]
    missing = _place_candidates(client, world.version.id, _lesson(world, "A1"), teacher_id=world.t2.id, room_id=999999)
    assert (missing.status_code, missing.json()["detail"]) == (404, "Room not found")


# --- Weekly periods and the lesson block rules after placing ---


def test_placing_the_whole_requirement_clears_weekly_periods(
    client: TestClient, db_session: Session
) -> None:
    """2+1: block 1 on Wednesday, the single lesson on Monday -- different
    days, so nothing is left."""
    world = _world(db_session, skip_rows=("S1", "S2", "S3"))
    h7 = [v for v in _check(client, world)["violations"] if v["type"] == "H7_WEEKLY_PERIODS"]
    assert [v["class_subject_requirement_id"] for v in h7] == [world.science.id]

    first = _ok(_place(client, world.version.id, _lesson(world, "S2"), world.slot(3, 6), teacher_id=world.t1.id))
    assert "H7_WEEKLY_PERIODS" in _types(first["check"])  # 2 of 3

    second = _ok(_place(client, world.version.id, _lesson(world, "S3"), world.slot(1, 3), teacher_id=world.t1.id))

    assert second["check"]["violations"] == []
    assert second["check"]["is_valid"] is True
    assert second["check"] == _check(client, world)
    assert _ok(_unscheduled(client, world.version.id))["lessons"] == []


def test_two_blocks_of_2_plus_1_on_the_same_day_are_reported(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("S1", "S2", "S3"))
    _ok(_place(client, world.version.id, _lesson(world, "S1"), world.slot(3, 5), teacher_id=world.t1.id))

    data = _ok(_place(client, world.version.id, _lesson(world, "S3"), world.slot(3, 3), teacher_id=world.t1.id))

    assert _types(data["check"]) == {"BLOCK_SAME_DAY"}
    assert data["check"] == _check(client, world)


def test_other_versions_of_the_semester_are_untouched(client: TestClient, db_session: Session) -> None:
    world = _world(db_session, skip_rows=("A1",))
    from app.models.schedule_version import ScheduleVersion

    other = ScheduleVersion(semester_id=world.version.semester_id, version_number=2, status="DRAFT")
    db_session.add(other)
    db_session.commit()

    _ok(_place(client, world.version.id, _lesson(world, "A1"), world.slot(3, 5), teacher_id=world.t2.id))

    assert _schedule_snapshot(db_session, other.id) == []
    assert len(_ok(_unscheduled(client, other.id))["lessons"]) == len(PLACEMENT)
