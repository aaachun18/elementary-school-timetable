"""Task 89: a lesson in a lesson block (連堂) moves, swaps and changes
teacher together with its whole block -- move-lesson, swap-lessons (preview
and execution) and move-candidates all follow services/block_adjustment.py.

Test data is written straight to the database through db_session.
"""

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear, Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class, Grade
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.subject import Subject
from app.models.teacher import Teacher, TeacherSubject
from app.models.time_slot import TimeSlot
from app.services import schedule_adjustment
from tests.test_move_candidates import _by_slot, _candidates
from tests.test_move_swap_lessons import _move, _ok, _swap

URL = "/api/v1/schedule-versions"
LUNCH = 4


@dataclass
class World:
    """One DRAFT version, class c1; weekdays 1-3, periods 1-3 and 5-6
    teaching, 4 is lunch. As built (valid, no violations):
    - science 2+1: S1 Mon 1, S2 Mon 2 (block 1); S3 Tue 1 (block 2)
    - math 2: M1 Tue 5, M2 Tue 6 (one block of 2)
    - english (no pattern): E1 Wed 1, E2 Wed 2
    - art (no pattern): A1 Mon 5
    Science and math by t1, english and art by t2; t3 can teach science."""

    db: Session
    version: ScheduleVersion
    t1: Teacher
    t2: Teacher
    t3: Teacher
    science: ClassSubjectRequirement
    slots: dict[tuple[int, int], TimeSlot]
    lessons: dict[str, Lesson]
    rows: dict[str, Schedule]

    def slot(self, weekday: int, period: int) -> int:
        return self.slots[(weekday, period)].id

    def row(self, name: str) -> int:
        return self.rows[name].id

    def where(self) -> dict[str, int | None]:
        """name -> time slot id of every row, as stored now."""
        self.db.expire_all()
        return {name: self.db.get(Schedule, row.id).time_slot_id for name, row in self.rows.items()}  # type: ignore[union-attr]


PLACEMENT = {
    "S1": (1, 1), "S2": (1, 2), "S3": (2, 1),
    "M1": (2, 5), "M2": (2, 6),
    "E1": (3, 1), "E2": (3, 2),
    "A1": (1, 5),
}


def _world(db: Session, *, skip_rows: tuple[str, ...] = ()) -> World:
    year = AcademicYear(year=8901, is_active=True)
    db.add(year)
    db.flush()
    semester = Semester(academic_year_id=year.id, number=1, is_active=True)
    grade = Grade(name="Grade 8901", level=8901)
    db.add_all([semester, grade])
    db.flush()
    slots = {
        (weekday, period): TimeSlot(weekday=weekday, period=period, is_teaching_period=period != LUNCH)
        for weekday in (1, 2, 3)
        for period in (1, 2, 3, 4, 5, 6)
    }
    db.add_all(slots.values())
    subjects = {name: Subject(name=name, is_active=True) for name in ("自然", "數學", "英文", "美勞")}
    c1 = Class(grade_id=grade.id, name="四年甲班", is_active=True)
    teachers = [
        Teacher(name=name, is_active=True, min_weekly_periods=0, max_weekly_periods=20)
        for name in ("一號老師", "二號老師", "三號老師")
    ]
    t1, t2, t3 = teachers
    db.add_all([*subjects.values(), c1, *teachers])
    db.flush()
    db.add_all(
        [TeacherSubject(teacher_id=t1.id, subject_id=subjects[name].id) for name in ("自然", "數學")]
        + [TeacherSubject(teacher_id=t2.id, subject_id=subjects[name].id) for name in ("英文", "美勞")]
        + [TeacherSubject(teacher_id=t3.id, subject_id=subjects["自然"].id)]
    )
    requirements = {
        "S": ClassSubjectRequirement(semester_id=semester.id, class_id=c1.id, subject_id=subjects["自然"].id, weekly_periods=3, lesson_pattern="2+1"),
        "M": ClassSubjectRequirement(semester_id=semester.id, class_id=c1.id, subject_id=subjects["數學"].id, weekly_periods=2, lesson_pattern="2"),
        "E": ClassSubjectRequirement(semester_id=semester.id, class_id=c1.id, subject_id=subjects["英文"].id, weekly_periods=2),
        "A": ClassSubjectRequirement(semester_id=semester.id, class_id=c1.id, subject_id=subjects["美勞"].id, weekly_periods=1),
    }
    db.add_all(requirements.values())
    db.flush()
    blocks = {"S1": (1, 1), "S2": (1, 2), "S3": (2, 1), "M1": (1, 1), "M2": (1, 2)}
    lessons: dict[str, Lesson] = {}
    for name in PLACEMENT:
        block_no, block_seq = blocks.get(name, (None, None))
        lessons[name] = Lesson(
            class_subject_requirement_id=requirements[name[0]].id,
            sequence_number=int(name[1]),
            block_no=block_no,
            block_seq=block_seq,
        )
    db.add_all(lessons.values())
    version = ScheduleVersion(semester_id=semester.id, version_number=1, status="DRAFT")
    db.add(version)
    db.flush()
    rows = {
        name: Schedule(
            schedule_version_id=version.id,
            lesson_id=lessons[name].id,
            teacher_id=(t1 if name[0] in "SM" else t2).id,
            time_slot_id=slots[PLACEMENT[name]].id,
        )
        for name in PLACEMENT
        if name not in skip_rows
    }
    db.add_all(rows.values())
    db.commit()
    return World(db, version, t1, t2, t3, requirements["S"], slots, lessons, rows)


def _check(client: TestClient, world: World) -> dict:
    return _ok(client.get(f"{URL}/{world.version.id}/check"))


def _moved(data: dict) -> dict[int, int | None]:
    return {change["schedule_id"]: change["new_time_slot_id"] for change in data["changes"]}


def _refused(response: Any, reason: str) -> None:
    assert response.status_code == 409, response.json()
    assert response.json()["reason"] == reason
    assert response.json()["detail"]


# --- Moving a whole block to free periods ---


@pytest.mark.parametrize(("dragged", "target"), [("S1", (3, 5)), ("S2", (3, 6))])
def test_move_starts_the_block_k_minus_1_periods_before_the_target(
    client: TestClient, db_session: Session, dragged: str, target: tuple[int, int]
) -> None:
    """Dropping lesson 1 on Wed 5, or lesson 2 on Wed 6: the block goes to
    Wed 5-6 either way, teacher unchanged."""
    world = _world(db_session)

    data = _ok(_move(client, world.version.id, world.row(dragged), world.slot(*target)))

    assert _moved(data) == {world.row("S1"): world.slot(3, 5), world.row("S2"): world.slot(3, 6)}
    assert data["check"]["violations"] == []
    db_session.expire_all()
    assert {db_session.get(Schedule, world.row(n)).teacher_id for n in ("S1", "S2")} == {world.t1.id}  # type: ignore[union-attr]


def test_move_may_overlap_the_blocks_own_periods(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    data = _ok(_move(client, world.version.id, world.row("S1"), world.slot(1, 2)))

    assert _moved(data) == {world.row("S1"): world.slot(1, 2), world.row("S2"): world.slot(1, 3)}


def test_move_with_target_room_puts_the_whole_block_there(
    client: TestClient, db_session: Session
) -> None:
    from app.models.room import Room

    world = _world(db_session)
    room = Room(name="自然教室", room_type="自然教室", is_active=True)
    db_session.add(room)
    db_session.commit()

    data = _ok(_move(client, world.version.id, world.row("S2"), world.slot(3, 6), room_id=room.id))

    assert {change["new_room_id"] for change in data["changes"]} == {room.id}
    assert len(data["changes"]) == 2


@pytest.mark.parametrize(
    ("dragged", "target", "why"),
    [
        ("S1", (1, 3), "the second lesson would fall on lunch"),
        ("S2", (1, 1), "the first lesson would need a period before period 1"),
        ("S1", (2, 6), "the second lesson would be after the last period"),
        ("S2", (2, 5), "the first lesson would fall on lunch (across lunch)"),
    ],
)
def test_move_out_of_range_is_refused_and_not_a_candidate(
    client: TestClient, db_session: Session, dragged: str, target: tuple[int, int], why: str
) -> None:
    world = _world(db_session)
    before = world.where()

    response = _move(client, world.version.id, world.row(dragged), world.slot(*target))
    candidate = _by_slot(_ok(_candidates(client, world.version.id, world.row(dragged))))[world.slot(*target)]

    _refused(response, "BLOCK_OUT_OF_RANGE")
    assert (candidate["available"], candidate["unavailable_reason"], candidate["move"]) == (
        False, "BLOCK_OUT_OF_RANGE", None,
    ), why
    assert world.where() == before


def test_move_onto_other_lessons_of_the_class_is_refused(
    client: TestClient, db_session: Session
) -> None:
    """Wed 1-2 hold E1 and E2: not a move but a swap -- and a block of two
    can't swap with one single lesson, so nothing is offered there."""
    world = _world(db_session)
    before = world.where()

    response = _move(client, world.version.id, world.row("S1"), world.slot(3, 1))
    candidate = _by_slot(_ok(_candidates(client, world.version.id, world.row("S1"))))[world.slot(3, 1)]

    _refused(response, "BLOCK_TARGET_OCCUPIED")
    assert candidate["unavailable_reason"] == "BLOCK_TARGET_OCCUPIED"
    assert candidate["swaps"] == []
    assert candidate["unsupported_swaps"] == [
        {"swap_with_schedule_id": world.row("E1"), "reason": "BLOCK_SWAP_UNSUPPORTED"}
    ]
    assert world.where() == before


def test_partly_placed_block_moves_the_lessons_it_has(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("S1",))

    data = _ok(_move(client, world.version.id, world.row("S2"), world.slot(3, 6)))

    assert _moved(data) == {world.row("S2"): world.slot(3, 6)}
    # The missing first lesson still needs its period: none before period 1.
    _refused(_move(client, world.version.id, world.row("S2"), world.slot(1, 1)), "BLOCK_OUT_OF_RANGE")


# --- Swapping ---


def test_two_blocks_of_two_swap_whole(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    data = _ok(_swap(client, world.version.id, world.row("S2"), world.row("M1")))

    assert _moved(data) == {
        world.row("S1"): world.slot(2, 5),
        world.row("S2"): world.slot(2, 6),
        world.row("M1"): world.slot(1, 1),
        world.row("M2"): world.slot(1, 2),
    }
    # Science's two blocks are now both on Tuesday -- reported, not refused.
    assert {v["type"] for v in data["check"]["violations"]} == {"BLOCK_SAME_DAY"}


@pytest.mark.parametrize(("first", "second"), [("A1", "E1"), ("S3", "A1")])
def test_single_lessons_swap_as_before(
    client: TestClient, db_session: Session, first: str, second: str
) -> None:
    """Two lessons of no block -- or the one-lesson block of 2+1 and a
    lesson of no block -- exchange time slots, nothing else moves."""
    world = _world(db_session)

    data = _ok(_swap(client, world.version.id, world.row(first), world.row(second)))

    assert _moved(data) == {
        world.row(first): world.slot(*PLACEMENT[second]),
        world.row(second): world.slot(*PLACEMENT[first]),
    }


@pytest.mark.parametrize(
    ("first", "second", "why"),
    [
        ("S1", "A1", "a block of two with a single lesson"),
        ("E1", "M2", "a single lesson with a block of two"),
        ("S1", "S2", "two lessons of the same block"),
    ],
)
def test_unsupported_swaps_are_refused(
    client: TestClient, db_session: Session, first: str, second: str, why: str
) -> None:
    world = _world(db_session)
    before = world.where()

    _refused(_swap(client, world.version.id, world.row(first), world.row(second)), "BLOCK_SWAP_UNSUPPORTED")
    assert world.where() == before, why


def test_swap_with_a_partly_placed_block_is_refused(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, skip_rows=("M2",))

    _refused(_swap(client, world.version.id, world.row("S1"), world.row("M1")), "BLOCK_SWAP_UNSUPPORTED")


def test_swap_with_a_block_and_several_single_lessons_is_not_offered(
    client: TestClient, db_session: Session
) -> None:
    """Dropping science block 1 on Wed 2 (E2, with E1 before it): the move
    lands on two other lessons and neither is a block of two."""
    world = _world(db_session)

    candidate = _by_slot(_ok(_candidates(client, world.version.id, world.row("S2"))))[world.slot(3, 2)]

    assert candidate["available"] is False
    assert candidate["unavailable_reason"] == "BLOCK_TARGET_OCCUPIED"
    assert candidate["swaps"] == []
    assert [item["swap_with_schedule_id"] for item in candidate["unsupported_swaps"]] == [world.row("E2")]


# --- Fixed lessons: not blocked, reported (decision 15) ---


def test_fixed_lesson_in_a_block_moves_with_it_and_is_reported(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.lessons["S2"].fixed_time_slot_id = world.slot(1, 2)
    db_session.commit()

    move = _ok(_move(client, world.version.id, world.row("S1"), world.slot(3, 5)))
    swap = _ok(_swap(client, world.version.id, world.row("S1"), world.row("M1")))

    assert len(move["changes"]) == 2
    assert [v["lesson_id"] for v in move["check"]["violations"] if v["type"] == "FIXED_TIME_SLOT_MISMATCH"] == [
        world.lessons["S2"].id
    ]
    assert len(swap["changes"]) == 4


# --- Changing teacher: the whole requirement, so every block, already ---


def test_reassign_changes_the_whole_block(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    body = {"class_subject_requirement_id": world.science.id, "new_teacher_id": world.t3.id}

    preview = _ok(client.post(f"{URL}/{world.version.id}/reassign-teacher", json={**body, "dry_run": True}))
    saved = _ok(client.post(f"{URL}/{world.version.id}/reassign-teacher", json=body))

    assert preview["check"] == saved["check"] == _check(client, world)
    assert saved["updated_schedule_row_count"] == 3
    db_session.expire_all()
    teachers = {db_session.get(Schedule, world.row(n)).teacher_id for n in ("S1", "S2", "S3")}  # type: ignore[union-attr]
    assert teachers == {world.t3.id}
    assert _check(client, world)["violations"] == []


# --- Consistency: preview = execution = /check = candidates ---


@pytest.mark.parametrize(
    "change",
    [
        ("move", "S2", (3, 6)),
        ("move", "S1", (1, 2)),
        ("move", "S3", (1, 5)),
        ("swap", "S1", "M2"),
        ("swap", "S3", "E1"),
    ],
)
def test_preview_matches_execution_and_check(
    client: TestClient, db_session: Session, change: tuple[str, str, Any]
) -> None:
    world = _world(db_session)
    kind, name, target = change

    def call(dry_run: bool) -> Any:
        if kind == "move":
            return _move(client, world.version.id, world.row(name), world.slot(*target), dry_run=dry_run)
        return _swap(client, world.version.id, world.row(name), world.row(target), dry_run=dry_run)

    before = _check(client, world)
    preview = _ok(call(True))
    assert _check(client, world) == before
    saved = _ok(call(False))

    assert preview["changes"] == saved["changes"]
    assert preview["check"] == saved["check"] == _check(client, world)


def test_candidates_match_previews_for_every_row(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    compared = refused = 0

    for name in PLACEMENT:
        data = _ok(_candidates(client, world.version.id, world.row(name)))
        assert data["baseline"] == _check(client, world)
        for candidate in data["candidates"]:
            slot_id = candidate["time_slot_id"]
            reason = candidate["unavailable_reason"]
            if candidate["available"]:
                preview = _ok(_move(client, world.version.id, world.row(name), slot_id, dry_run=True))
                assert candidate["move"] == preview["check"], (name, slot_id)
                members = candidate["block_members"]
                if members is not None:
                    planned = {m["schedule_id"]: m["to_time_slot_id"] for m in members}
                    assert _moved(preview).items() <= planned.items()
                compared += 1
            elif reason is not None and reason.startswith("BLOCK_"):
                _refused(_move(client, world.version.id, world.row(name), slot_id, dry_run=True), reason)
                refused += 1
            for swap in candidate["swaps"]:
                preview = _ok(_swap(client, world.version.id, world.row(name), swap["swap_with_schedule_id"], dry_run=True))
                assert swap["check"] == preview["check"]
            for item in candidate["unsupported_swaps"] or []:
                _refused(
                    _swap(client, world.version.id, world.row(name), item["swap_with_schedule_id"], dry_run=True),
                    item["reason"],
                )
                refused += 1

    assert compared > 0 and refused > 0
    assert _check(client, world)["violations"] == []  # every preview was read-only


def test_candidates_of_a_lesson_without_block_have_no_block_fields(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)

    data = _ok(_candidates(client, world.version.id, world.row("A1")))

    for candidate in data["candidates"]:
        assert candidate["block_members"] is None
        assert all(swap["block_members"] is None for swap in candidate["swaps"])
    # Mon 1 holds S1 (block of two): offered as unsupported, not as a swap.
    monday_1 = _by_slot(data)[world.slot(1, 1)]
    assert monday_1["swaps"] == []
    assert monday_1["unsupported_swaps"] == [
        {"swap_with_schedule_id": world.row("S1"), "reason": "BLOCK_SWAP_UNSUPPORTED"}
    ]
    # A move onto it is still allowed for a single lesson (H2 reported).
    assert monday_1["available"] is True
    assert "H2_CLASS_CONFLICT" in {v["type"] for v in monday_1["move"]["violations"]}


def test_block_members_for_a_block_move_and_swap(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    data = _by_slot(_ok(_candidates(client, world.version.id, world.row("S2"))))

    assert data[world.slot(3, 6)]["block_members"] == [
        {"schedule_id": world.row("S1"), "to_time_slot_id": world.slot(3, 5)},
        {"schedule_id": world.row("S2"), "to_time_slot_id": world.slot(3, 6)},
    ]
    [swap] = data[world.slot(2, 5)]["swaps"]
    assert swap["swap_with_schedule_id"] == world.row("M1")
    assert {m["schedule_id"]: m["to_time_slot_id"] for m in swap["block_members"]} == {
        world.row("S1"): world.slot(2, 5),
        world.row("S2"): world.slot(2, 6),
        world.row("M1"): world.slot(1, 1),
        world.row("M2"): world.slot(1, 2),
    }


# --- Atomicity ---


def test_failure_halfway_through_a_block_changes_nothing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = _world(db_session)
    before = world.where()
    real_apply = schedule_adjustment._apply
    calls: list[int] = []

    def failing_apply(schedule: Schedule, time_slot_id: int | None, room_id: int | None) -> Any:
        calls.append(schedule.id)
        if len(calls) == 2:
            raise RuntimeError("simulated failure on the second lesson")
        return real_apply(schedule, time_slot_id, room_id)

    monkeypatch.setattr(schedule_adjustment, "_apply", failing_apply)

    with pytest.raises(RuntimeError):
        schedule_adjustment.move_lesson(
            db_session, world.version.id, world.row("S1"), world.slot(3, 5), None, dry_run=False
        )

    assert len(calls) == 2
    assert world.where() == before


# --- Permissions and version status (existing guards) ---


def test_teacher_gets_403_for_block_moves(
    teacher_client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)

    assert _move(teacher_client, world.version.id, world.row("S1"), world.slot(3, 5)).status_code == 403
    assert _swap(teacher_client, world.version.id, world.row("S1"), world.row("M1")).status_code == 403
    assert _candidates(teacher_client, world.version.id, world.row("S1")).status_code == 403


@pytest.mark.parametrize("status", ["PUBLISHED", "ARCHIVED"])
def test_locked_version_returns_409_before_block_rules(
    client: TestClient, db_session: Session, status: str
) -> None:
    world = _world(db_session)
    world.version.status = status
    db_session.commit()
    before = world.where()

    # Out of range for the block, but the lock is reported first.
    move = _move(client, world.version.id, world.row("S1"), world.slot(1, 3))
    swap = _swap(client, world.version.id, world.row("S1"), world.row("M1"))

    assert move.status_code == swap.status_code == 409
    assert "reason" not in move.json()
    assert world.where() == before


def test_rows_of_other_versions_are_untouched(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    other = ScheduleVersion(semester_id=world.version.semester_id, version_number=2, status="DRAFT")
    db_session.add(other)
    db_session.flush()
    copy = Schedule(
        schedule_version_id=other.id,
        lesson_id=world.lessons["S2"].id,
        teacher_id=world.t1.id,
        time_slot_id=world.slot(1, 2),
    )
    db_session.add(copy)
    db_session.commit()

    _ok(_move(client, world.version.id, world.row("S1"), world.slot(3, 5)))

    db_session.expire_all()
    assert db_session.scalars(select(Schedule.time_slot_id).where(Schedule.id == copy.id)).one() == world.slot(1, 2)
