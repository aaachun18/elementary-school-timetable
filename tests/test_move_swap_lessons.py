from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.subject import Subject
from app.models.teacher import Teacher, TeacherAvailability
from app.services import schedule_adjustment, schedule_check
from tests.test_reassign_teacher import Builder

# Task 65: POST /api/v1/schedule-versions/{id}/move-lesson and
# /swap-lessons. Test data is written straight to the database through
# db_session (the same session the client fixtures' requests use).


@dataclass
class Timetable:
    """One DRAFT version, valid as built (slots 0..5 on one weekday):
    - c1 English: 2 periods by t1, slots 0 and 1 (the first in room r1)
    - c1 Science: 1 period by t2, slot 2
    - c2 English: 1 period by t1, slot 3
    Both teachers are qualified for both subjects."""

    builder: Builder
    version: ScheduleVersion
    t1: Teacher
    t2: Teacher
    english: Subject
    science: Subject
    c1: Class
    c2: Class
    r1: Room
    r2: Room
    c1_english: list[Schedule]
    c1_science: Schedule
    c2_english: Schedule

    def slot(self, index: int) -> int:
        return self.builder.slots[index].id


def _row_of(db: Session, version_id: int, requirement: ClassSubjectRequirement) -> list[Schedule]:
    return list(
        db.scalars(
            select(Schedule)
            .join(Lesson, Schedule.lesson_id == Lesson.id)
            .where(
                Schedule.schedule_version_id == version_id,
                Lesson.class_subject_requirement_id == requirement.id,
            )
            .order_by(Schedule.id)
        ).all()
    )


def _build_timetable(db: Session) -> Timetable:
    builder = Builder(db)
    english = builder.subject("英文")
    science = builder.subject("自然")
    t1 = builder.teacher("一號老師", [english, science])
    t2 = builder.teacher("二號老師", [english, science])
    c1 = builder.class_("四年甲班")
    c2 = builder.class_("四年乙班")
    r1 = Room(name="Room 1", room_type="一般教室", is_active=True)
    r2 = Room(name="Room 2", room_type="一般教室", is_active=True)
    db.add_all([r1, r2])
    db.commit()
    version = builder.version()
    c1_english_req = builder.course(version, c1, english, t1, [0, 1])
    c1_science_req = builder.course(version, c1, science, t2, [2])
    c2_english_req = builder.course(version, c2, english, t1, [3])
    c1_english = _row_of(db, version.id, c1_english_req)
    c1_english[0].room_id = r1.id
    db.commit()
    return Timetable(
        builder=builder,
        version=version,
        t1=t1,
        t2=t2,
        english=english,
        science=science,
        c1=c1,
        c2=c2,
        r1=r1,
        r2=r2,
        c1_english=c1_english,
        c1_science=_row_of(db, version.id, c1_science_req)[0],
        c2_english=_row_of(db, version.id, c2_english_req)[0],
    )


# --- Request / inspection helpers ---


def _move(
    client: TestClient,
    version_id: int,
    schedule_id: int,
    time_slot_id: int,
    *,
    room_id: int | None = None,
    dry_run: bool | None = None,
) -> Any:
    body: dict[str, Any] = {"schedule_id": schedule_id, "target_time_slot_id": time_slot_id}
    if room_id is not None:
        body["target_room_id"] = room_id
    if dry_run is not None:
        body["dry_run"] = dry_run
    return client.post(f"/api/v1/schedule-versions/{version_id}/move-lesson", json=body)


def _swap(
    client: TestClient,
    version_id: int,
    schedule_id: int,
    other_id: int,
    *,
    dry_run: bool | None = None,
) -> Any:
    body: dict[str, Any] = {"schedule_id": schedule_id, "swap_with_schedule_id": other_id}
    if dry_run is not None:
        body["dry_run"] = dry_run
    return client.post(f"/api/v1/schedule-versions/{version_id}/swap-lessons", json=body)


def _ok(response: Any) -> dict:
    assert response.status_code == 200, response.json()
    data: dict = response.json()
    return data


def _violation_types(data: dict) -> set[str]:
    return {v["type"] for v in data["check"]["violations"]}


def _schedule_snapshot(db: Session, version_id: int | None = None) -> list[tuple[object, ...]]:
    """Every column of every Schedule row (optionally of one version)."""
    db.expire_all()
    columns = list(Schedule.__table__.columns.keys())
    stmt = select(Schedule).order_by(Schedule.id)
    if version_id is not None:
        stmt = stmt.where(Schedule.schedule_version_id == version_id)
    return [tuple(getattr(row, c) for c in columns) for row in db.scalars(stmt).all()]


def _get(db: Session, schedule_id: int) -> Schedule:
    db.expire_all()
    row = db.get(Schedule, schedule_id)
    assert row is not None
    return row


# --- Move ---


def test_move_changes_only_time_slot(client: TestClient, db_session: Session) -> None:
    tt = _build_timetable(db_session)
    row = tt.c1_english[0]
    before = {r[0]: r for r in _schedule_snapshot(db_session, tt.version.id)}

    data = _ok(_move(client, tt.version.id, row.id, tt.slot(4)))

    assert data["schedule_version_id"] == tt.version.id
    assert data["dry_run"] is False
    assert data["changes"] == [
        {
            "schedule_id": row.id,
            "previous_time_slot_id": tt.slot(0),
            "new_time_slot_id": tt.slot(4),
            "previous_room_id": tt.r1.id,
            "new_room_id": tt.r1.id,
        }
    ]
    moved = _get(db_session, row.id)
    assert (moved.time_slot_id, moved.teacher_id, moved.room_id, moved.lesson_id) == (
        tt.slot(4),
        tt.t1.id,
        tt.r1.id,
        row.lesson_id,
    )
    after = {r[0]: r for r in _schedule_snapshot(db_session, tt.version.id)}
    assert {k: v for k, v in after.items() if k != row.id} == {
        k: v for k, v in before.items() if k != row.id
    }


def test_move_with_target_room_changes_room(client: TestClient, db_session: Session) -> None:
    tt = _build_timetable(db_session)
    row = tt.c1_english[0]

    data = _ok(_move(client, tt.version.id, row.id, tt.slot(4), room_id=tt.r2.id))

    assert data["changes"][0]["new_room_id"] == tt.r2.id
    assert _get(db_session, row.id).room_id == tt.r2.id


def test_move_to_same_slot_is_a_no_op(client: TestClient, db_session: Session) -> None:
    tt = _build_timetable(db_session)
    before = _schedule_snapshot(db_session)

    data = _ok(_move(client, tt.version.id, tt.c1_english[0].id, tt.slot(0)))

    assert data["changes"] == []
    assert data["check"]["is_valid"] is True
    assert _schedule_snapshot(db_session) == before


def test_move_into_teacher_conflict_is_reported(
    client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)

    # c2 English (t1) into slot 0, where t1 already teaches c1 English.
    data = _ok(_move(client, tt.version.id, tt.c2_english.id, tt.slot(0)))

    assert "H1_TEACHER_CONFLICT" in _violation_types(data)
    assert "H2_CLASS_CONFLICT" not in _violation_types(data)


def test_move_into_class_conflict_is_reported(
    client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)

    # c1 Science (t2) into slot 0, where c1 already has English -- not
    # turned into a swap.
    data = _ok(_move(client, tt.version.id, tt.c1_science.id, tt.slot(0)))

    assert "H2_CLASS_CONFLICT" in _violation_types(data)
    assert "H1_TEACHER_CONFLICT" not in _violation_types(data)
    assert _get(db_session, tt.c1_english[0].id).time_slot_id == tt.slot(0)


def test_move_into_unavailable_slot_is_reported(
    client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)
    db_session.add(TeacherAvailability(teacher_id=tt.t2.id, time_slot_id=tt.slot(4)))
    db_session.commit()

    data = _ok(_move(client, tt.version.id, tt.c1_science.id, tt.slot(4)))

    assert "H4_TEACHER_AVAILABILITY" in _violation_types(data)


def test_move_fixed_lesson_keeps_its_fixed_slot(
    client: TestClient, db_session: Session
) -> None:
    # Task 66: the move is still saved, but the check now reports it as
    # FIXED_TIME_SLOT_MISMATCH (Task 65 reported it as valid). The move must
    # leave the Lesson itself -- its fixed_time_slot_id -- untouched.
    tt = _build_timetable(db_session)
    lesson = db_session.get(Lesson, tt.c1_science.lesson_id)
    assert lesson is not None
    lesson.fixed_time_slot_id = tt.slot(2)
    db_session.commit()

    data = _ok(_move(client, tt.version.id, tt.c1_science.id, tt.slot(5)))

    assert _violation_types(data) == {"FIXED_TIME_SLOT_MISMATCH"}
    assert _get(db_session, tt.c1_science.id).time_slot_id == tt.slot(5)
    db_session.expire_all()
    assert db_session.get(Lesson, tt.c1_science.lesson_id).fixed_time_slot_id == tt.slot(2)


def test_move_without_conflict_is_valid(client: TestClient, db_session: Session) -> None:
    tt = _build_timetable(db_session)

    data = _ok(_move(client, tt.version.id, tt.c1_science.id, tt.slot(5)))

    assert data["check"]["is_valid"] is True
    assert data["check"]["violation_count"] == 0


# --- Swap ---


def test_swap_exchanges_time_slots_only(client: TestClient, db_session: Session) -> None:
    tt = _build_timetable(db_session)
    english, science = tt.c1_english[0], tt.c1_science

    data = _ok(_swap(client, tt.version.id, english.id, science.id))

    assert sorted(data["changes"], key=lambda c: c["schedule_id"]) == sorted(
        [
            {
                "schedule_id": english.id,
                "previous_time_slot_id": tt.slot(0),
                "new_time_slot_id": tt.slot(2),
                "previous_room_id": tt.r1.id,
                "new_room_id": tt.r1.id,
            },
            {
                "schedule_id": science.id,
                "previous_time_slot_id": tt.slot(2),
                "new_time_slot_id": tt.slot(0),
                "previous_room_id": None,
                "new_room_id": None,
            },
        ],
        key=lambda c: c["schedule_id"],
    )
    swapped_english, swapped_science = _get(db_session, english.id), _get(db_session, science.id)
    assert (swapped_english.time_slot_id, swapped_english.teacher_id, swapped_english.room_id) == (
        tt.slot(2),
        tt.t1.id,
        tt.r1.id,
    )
    assert (swapped_science.time_slot_id, swapped_science.teacher_id, swapped_science.room_id) == (
        tt.slot(0),
        tt.t2.id,
        None,
    )


def test_swap_within_class_without_conflict_is_valid(
    client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)

    data = _ok(_swap(client, tt.version.id, tt.c1_english[0].id, tt.c1_science.id))

    assert data["check"]["is_valid"] is True


def test_swap_into_teacher_conflict_is_reported(
    client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)
    # c2 Science by t2 in slot 0; swapping it with c2 English (t1, slot 3)
    # puts t1 in slot 0 twice (c1 English is there).
    c2_science_req = tt.builder.course(tt.version, tt.c2, tt.science, tt.t2, [0])
    c2_science = _row_of(db_session, tt.version.id, c2_science_req)[0]

    data = _ok(_swap(client, tt.version.id, tt.c2_english.id, c2_science.id))

    h1 = [v for v in data["check"]["violations"] if v["type"] == "H1_TEACHER_CONFLICT"]
    assert {v["teacher_id"] for v in h1} == {tt.t1.id}


def test_swap_with_itself_returns_409(client: TestClient, db_session: Session) -> None:
    tt = _build_timetable(db_session)
    before = _schedule_snapshot(db_session)

    response = _swap(client, tt.version.id, tt.c1_science.id, tt.c1_science.id)

    assert response.status_code == 409
    assert response.json()["detail"] == "不能與自己對調"
    assert _schedule_snapshot(db_session) == before


def test_swap_with_row_of_other_version_returns_409(
    client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)
    other_id = client.post(f"/api/v1/schedule-versions/{tt.version.id}/copy").json()["id"]
    other_row = _schedule_snapshot(db_session, other_id)[0]
    before = _schedule_snapshot(db_session)

    response = _swap(client, tt.version.id, tt.c1_science.id, other_row[0])

    assert response.status_code == 409
    assert response.json()["detail"] == "此排課紀錄不屬於該課表"
    assert _schedule_snapshot(db_session) == before


# --- dry_run ---


def test_move_dry_run_saves_nothing(client: TestClient, db_session: Session) -> None:
    tt = _build_timetable(db_session)
    before = _schedule_snapshot(db_session)

    data = _ok(_move(client, tt.version.id, tt.c2_english.id, tt.slot(0), dry_run=True))

    assert data["dry_run"] is True
    assert len(data["changes"]) == 1
    assert "H1_TEACHER_CONFLICT" in _violation_types(data)
    assert _schedule_snapshot(db_session) == before

    _ok(_move(client, tt.version.id, tt.c2_english.id, tt.slot(0), dry_run=False))
    assert _get(db_session, tt.c2_english.id).time_slot_id == tt.slot(0)


def test_swap_dry_run_saves_nothing(client: TestClient, db_session: Session) -> None:
    tt = _build_timetable(db_session)
    c2_science_req = tt.builder.course(tt.version, tt.c2, tt.science, tt.t2, [0])
    c2_science = _row_of(db_session, tt.version.id, c2_science_req)[0]
    before = _schedule_snapshot(db_session)

    data = _ok(_swap(client, tt.version.id, tt.c2_english.id, c2_science.id, dry_run=True))

    assert data["dry_run"] is True
    assert len(data["changes"]) == 2
    assert "H1_TEACHER_CONFLICT" in _violation_types(data)
    assert _schedule_snapshot(db_session) == before

    _ok(_swap(client, tt.version.id, tt.c2_english.id, c2_science.id))
    assert _get(db_session, tt.c2_english.id).time_slot_id == tt.slot(0)


# --- Refusals: nothing may change ---


@pytest.mark.parametrize(
    ("case", "expected_detail"),
    [
        ("missing_version", "ScheduleVersion not found"),
        ("missing_schedule", "Schedule not found"),
        ("missing_time_slot", "TimeSlot not found"),
        ("missing_room", "Room not found"),
    ],
)
def test_move_missing_record_returns_404(
    client: TestClient, db_session: Session, case: str, expected_detail: str
) -> None:
    tt = _build_timetable(db_session)
    before = _schedule_snapshot(db_session)
    version_id, schedule_id, slot_id, room_id = (
        tt.version.id,
        tt.c1_science.id,
        tt.slot(5),
        None,
    )
    if case == "missing_version":
        version_id = 999999
    elif case == "missing_schedule":
        schedule_id = 999999
    elif case == "missing_time_slot":
        slot_id = 999999
    else:
        room_id = 999999

    response = _move(client, version_id, schedule_id, slot_id, room_id=room_id)

    assert response.status_code == 404
    assert response.json()["detail"] == expected_detail
    assert _schedule_snapshot(db_session) == before


def test_move_row_of_other_version_returns_409(
    client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)
    other_id = client.post(f"/api/v1/schedule-versions/{tt.version.id}/copy").json()["id"]
    other_row_id = _schedule_snapshot(db_session, other_id)[0][0]
    before = _schedule_snapshot(db_session)

    response = _move(client, tt.version.id, other_row_id, tt.slot(5))

    assert response.status_code == 409
    assert response.json()["detail"] == "此排課紀錄不屬於該課表"
    assert _schedule_snapshot(db_session) == before


@pytest.mark.parametrize(
    ("status", "expected_detail"),
    [
        ("PUBLISHED", "已發布版本不可修改，請建立新草稿版本"),
        ("ARCHIVED", "已封存的課表無法修改，請先複製成新草稿"),
    ],
)
def test_move_and_swap_in_locked_version_return_409(
    client: TestClient, db_session: Session, status: str, expected_detail: str
) -> None:
    tt = _build_timetable(db_session)
    version = db_session.get(ScheduleVersion, tt.version.id)
    assert version is not None
    version.status = status
    db_session.commit()
    before = _schedule_snapshot(db_session)

    move = _move(client, tt.version.id, tt.c1_science.id, tt.slot(5))
    swap = _swap(client, tt.version.id, tt.c1_english[0].id, tt.c1_science.id)

    for response in (move, swap):
        assert response.status_code == 409
        assert response.json()["detail"] == expected_detail
    assert _schedule_snapshot(db_session) == before


# --- Isolation ---


def test_move_leaves_other_version_of_same_semester_alone(
    client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)
    other_id = client.post(f"/api/v1/schedule-versions/{tt.version.id}/copy").json()["id"]
    other_before = _schedule_snapshot(db_session, other_id)

    _ok(_move(client, tt.version.id, tt.c1_science.id, tt.slot(5)))
    _ok(_swap(client, tt.version.id, tt.c1_english[0].id, tt.c2_english.id))

    assert _schedule_snapshot(db_session, other_id) == other_before


def test_move_in_cross_semester_copy_leaves_source_alone(
    client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)
    target_semester = tt.builder.semester_in_year(number=2)
    copy_id = client.post(
        f"/api/v1/schedule-versions/{tt.version.id}/copy",
        json={"target_semester_id": target_semester.id},
    ).json()["id"]
    source_before = _schedule_snapshot(db_session, tt.version.id)
    copied_row_id = _schedule_snapshot(db_session, copy_id)[0][0]

    _ok(_move(client, copy_id, copied_row_id, tt.slot(5)))

    assert _get(db_session, copied_row_id).time_slot_id == tt.slot(5)
    assert _schedule_snapshot(db_session, tt.version.id) == source_before


# --- Atomicity ---


def _fail(*args: object, **kwargs: object) -> None:
    raise RuntimeError("simulated failure during the schedule check")


def test_move_failure_during_check_rolls_back(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tt = _build_timetable(db_session)
    before = _schedule_snapshot(db_session)
    monkeypatch.setattr(schedule_check, "check_schedule_version", _fail)

    with pytest.raises(RuntimeError):
        schedule_adjustment.move_lesson(
            db_session, tt.version.id, tt.c1_science.id, tt.slot(5), None, dry_run=False
        )

    assert _schedule_snapshot(db_session) == before


def test_swap_failure_during_check_rolls_back(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tt = _build_timetable(db_session)
    before = _schedule_snapshot(db_session)
    monkeypatch.setattr(schedule_check, "check_schedule_version", _fail)

    with pytest.raises(RuntimeError):
        schedule_adjustment.swap_lessons(
            db_session, tt.version.id, tt.c1_english[0].id, tt.c1_science.id, dry_run=False
        )

    assert _schedule_snapshot(db_session) == before


# --- Permissions ---


def test_move_and_swap_unauthenticated_return_401(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)

    move = _move(unauthenticated_client, tt.version.id, tt.c1_science.id, tt.slot(5))
    swap = _swap(unauthenticated_client, tt.version.id, tt.c1_english[0].id, tt.c1_science.id)

    assert move.status_code == 401
    assert swap.status_code == 401


def test_move_and_swap_as_teacher_return_403(
    teacher_client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)
    before = _schedule_snapshot(db_session)

    move = _move(teacher_client, tt.version.id, tt.c1_science.id, tt.slot(5))
    swap = _swap(teacher_client, tt.version.id, tt.c1_english[0].id, tt.c1_science.id)

    assert move.status_code == 403
    assert swap.status_code == 403
    assert _schedule_snapshot(db_session) == before


# --- The school office's sequence: copy -> reassign -> move ---


def test_copy_reassign_then_move_resolves_conflict(
    client: TestClient, db_session: Session
) -> None:
    tt = _build_timetable(db_session)
    # t3 teaches c3 English in slot 3 -- the same slot as c2 English.
    t3 = tt.builder.teacher("三號老師", [tt.english])
    c3 = tt.builder.class_("四年丙班")
    tt.builder.course(tt.version, c3, tt.english, t3, [3])
    assert client.get(f"/api/v1/schedule-versions/{tt.version.id}/check").json()["is_valid"]

    copy_id = client.post(f"/api/v1/schedule-versions/{tt.version.id}/copy").json()["id"]
    c2_english_requirement = db_session.scalars(
        select(ClassSubjectRequirement).where(
            ClassSubjectRequirement.class_id == tt.c2.id,
            ClassSubjectRequirement.subject_id == tt.english.id,
        )
    ).one()
    reassign = client.post(
        f"/api/v1/schedule-versions/{copy_id}/reassign-teacher",
        json={"class_subject_requirement_id": c2_english_requirement.id, "new_teacher_id": t3.id},
    ).json()
    assert "H1_TEACHER_CONFLICT" in {v["type"] for v in reassign["check"]["violations"]}

    copied_c2_english = _row_of(db_session, copy_id, c2_english_requirement)[0]
    moved = _ok(_move(client, copy_id, copied_c2_english.id, tt.slot(4)))

    assert moved["check"]["is_valid"] is True
    assert client.get(f"/api/v1/schedule-versions/{copy_id}/check").json()["is_valid"] is True
