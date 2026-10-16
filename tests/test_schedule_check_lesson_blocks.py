"""Task 88: the schedule check (GET /schedule-versions/{id}/check, and
everything built on check_assignments(): move / swap / reassign previews and
move-candidates) reports lesson block (連堂) violations:

- BLOCK_NOT_CONSECUTIVE: one block not on one day in adjacent teaching
  periods in block order, or not one teacher and one room;
- BLOCK_SAME_DAY: two blocks of one requirement on the same day.

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
from tests.test_move_candidates import _by_slot, _candidates
from tests.test_move_swap_lessons import _move, _ok, _swap

URL = "/api/v1/schedule-versions"
BLOCK_TYPES = {"BLOCK_NOT_CONSECUTIVE", "BLOCK_SAME_DAY"}
LUNCH = 3


@dataclass
class World:
    """One DRAFT version. Weekdays 1-3, periods 1, 2, 3 (lunch, not a
    teaching period), 4, 5. Class c1:
    - science, lesson_pattern 2+1: block 1 = science[0], science[1];
      block 2 = science[2]; nothing placed yet (place() adds rows);
    - english, no pattern, 2 lessons (english[0..1]), no rows yet.
    Teachers t1 and t2 are qualified for both subjects."""

    db: Session
    version: ScheduleVersion
    t1: Teacher
    t2: Teacher
    c1: Class
    science_requirement: ClassSubjectRequirement
    english_requirement: ClassSubjectRequirement
    science: list[Lesson]
    english: list[Lesson]
    slots: dict[tuple[int, int], TimeSlot]

    def slot(self, weekday: int, period: int) -> int:
        return self.slots[(weekday, period)].id

    def place(
        self,
        lesson: Lesson,
        weekday: int | None,
        period: int | None,
        teacher: Teacher | None = None,
        *,
        no_teacher: bool = False,
    ) -> Schedule:
        row = Schedule(
            schedule_version_id=self.version.id,
            lesson_id=lesson.id,
            teacher_id=None if no_teacher else (teacher or self.t1).id,
            time_slot_id=None if weekday is None or period is None else self.slot(weekday, period),
        )
        self.db.add(row)
        self.db.commit()
        return row


def _world(db: Session) -> World:
    year = AcademicYear(year=8801, is_active=True)
    db.add(year)
    db.flush()
    semester = Semester(academic_year_id=year.id, number=1, is_active=True)
    grade = Grade(name="Grade 8801", level=8801)
    db.add_all([semester, grade])
    db.flush()
    slots = {
        (weekday, period): TimeSlot(
            weekday=weekday, period=period, is_teaching_period=period != LUNCH
        )
        for weekday in (1, 2, 3)
        for period in (1, 2, 3, 4, 5)
    }
    db.add_all(slots.values())
    science = Subject(name="自然", is_active=True)
    english = Subject(name="英文", is_active=True)
    c1 = Class(grade_id=grade.id, name="四年甲班", is_active=True)
    t1 = Teacher(name="一號老師", is_active=True, min_weekly_periods=0, max_weekly_periods=20)
    t2 = Teacher(name="二號老師", is_active=True, min_weekly_periods=0, max_weekly_periods=20)
    db.add_all([science, english, c1, t1, t2])
    db.flush()
    db.add_all(
        [
            TeacherSubject(teacher_id=teacher.id, subject_id=subject.id)
            for teacher in (t1, t2)
            for subject in (science, english)
        ]
    )
    science_requirement = ClassSubjectRequirement(
        semester_id=semester.id,
        class_id=c1.id,
        subject_id=science.id,
        weekly_periods=3,
        lesson_pattern="2+1",
    )
    english_requirement = ClassSubjectRequirement(
        semester_id=semester.id, class_id=c1.id, subject_id=english.id, weekly_periods=2
    )
    db.add_all([science_requirement, english_requirement])
    db.flush()
    science_lessons = [
        Lesson(
            class_subject_requirement_id=science_requirement.id,
            sequence_number=number,
            block_no=block_no,
            block_seq=block_seq,
        )
        for number, (block_no, block_seq) in enumerate([(1, 1), (1, 2), (2, 1)], start=1)
    ]
    english_lessons = [
        Lesson(class_subject_requirement_id=english_requirement.id, sequence_number=number)
        for number in (1, 2)
    ]
    db.add_all(science_lessons + english_lessons)
    version = ScheduleVersion(semester_id=semester.id, version_number=1, status="DRAFT")
    db.add(version)
    db.commit()
    return World(
        db=db,
        version=version,
        t1=t1,
        t2=t2,
        c1=c1,
        science_requirement=science_requirement,
        english_requirement=english_requirement,
        science=science_lessons,
        english=english_lessons,
        slots=slots,
    )


def _check(client: TestClient, world: World) -> dict:
    return _ok(client.get(f"{URL}/{world.version.id}/check"))


def _block_violations(check: dict) -> list[dict]:
    return [v for v in check["violations"] if v["type"] in BLOCK_TYPES]


def _place_valid_science(world: World) -> list[Schedule]:
    """Block 1 on Monday periods 1-2, block 2 on Tuesday period 1."""
    return [
        world.place(world.science[0], 1, 1),
        world.place(world.science[1], 1, 2),
        world.place(world.science[2], 2, 1),
    ]


def _place_english(world: World) -> list[Schedule]:
    return [world.place(world.english[0], 3, 1), world.place(world.english[1], 3, 4)]


# --- Each case ---


def test_valid_blocks_are_not_reported(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    _place_valid_science(world)
    _place_english(world)

    check = _check(client, world)

    assert check == {
        "schedule_version_id": world.version.id,
        "is_valid": True,
        "violation_count": 0,
        "violations": [],
    }


def test_block_across_lunch_is_not_consecutive(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)
    first = world.place(world.science[0], 1, 2)
    second = world.place(world.science[1], 1, 4)  # period 3 (lunch) in between
    world.place(world.science[2], 2, 1)

    violations = _block_violations(_check(client, world))

    assert sorted((v["type"], v["schedule_id"]) for v in violations) == [
        ("BLOCK_NOT_CONSECUTIVE", first.id),
        ("BLOCK_NOT_CONSECUTIVE", second.id),
    ]
    for violation in violations:
        assert violation["severity"] == "ERROR"
        assert violation["class_subject_requirement_id"] == world.science_requirement.id
        assert violation["class_id"] == world.c1.id
        assert violation["subject_id"] == world.science_requirement.subject_id
        assert violation["block_no"] == 1
        assert violation["identity_key"] == (
            f"BLOCK_NOT_CONSECUTIVE:{world.science_requirement.id}:1"
        )


def test_block_split_across_days_is_not_consecutive(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.place(world.science[0], 1, 1)
    world.place(world.science[1], 3, 2)
    world.place(world.science[2], 2, 1)

    violations = _block_violations(_check(client, world))

    assert {(v["type"], v["lesson_id"]) for v in violations} == {
        ("BLOCK_NOT_CONSECUTIVE", world.science[0].id),
        ("BLOCK_NOT_CONSECUTIVE", world.science[1].id),
    }


def test_block_in_reverse_order_is_not_consecutive(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.place(world.science[0], 1, 2)
    world.place(world.science[1], 1, 1)
    world.place(world.science[2], 2, 1)

    assert {v["type"] for v in _block_violations(_check(client, world))} == {
        "BLOCK_NOT_CONSECUTIVE"
    }


def test_block_with_two_teachers_is_not_consecutive(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.place(world.science[0], 1, 1)
    world.place(world.science[1], 1, 2, world.t2)
    world.place(world.science[2], 2, 1)

    assert {v["type"] for v in _block_violations(_check(client, world))} == {
        "BLOCK_NOT_CONSECUTIVE"
    }


def test_two_blocks_on_the_same_day_are_reported(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    rows = [
        world.place(world.science[0], 1, 1),
        world.place(world.science[1], 1, 2),
        world.place(world.science[2], 1, 4),
    ]

    violations = _block_violations(_check(client, world))

    assert sorted((v["type"], v["schedule_id"], v["block_no"]) for v in violations) == [
        ("BLOCK_SAME_DAY", rows[0].id, 1),
        ("BLOCK_SAME_DAY", rows[1].id, 1),
        ("BLOCK_SAME_DAY", rows[2].id, 2),
    ]
    assert {v["identity_key"] for v in violations} == {
        f"BLOCK_SAME_DAY:{world.science_requirement.id}:1,2"
    }
    assert all(v["severity"] == "ERROR" for v in violations)


def test_blocks_on_different_days_are_not_reported(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.place(world.science[0], 2, 4)
    world.place(world.science[1], 2, 5)
    world.place(world.science[2], 3, 2)

    assert _block_violations(_check(client, world)) == []


# --- A block placed only in part ---


def test_partly_placed_block_is_left_to_h7_and_incomplete_rows(
    client: TestClient, db_session: Session
) -> None:
    """Block 1 has one lesson in Monday period 1 and the other with no row
    at all; block 2's lesson has a row without a time slot. Nothing is
    wrong with the block itself yet -- the missing lessons are what H7 and
    INCOMPLETE_SCHEDULE_ROW report, exactly as for lessons in no block."""
    world = _world(db_session)
    world.place(world.science[0], 1, 1)
    world.place(world.science[2], None, None)

    types = {v["type"] for v in _check(client, world)["violations"]}

    assert types == {"H7_WEEKLY_PERIODS", "INCOMPLETE_SCHEDULE_ROW"}


@pytest.mark.parametrize(
    ("lesson_index", "period", "flagged"),
    [
        (0, 1, False),  # the second lesson can still go into period 2
        (0, 2, True),  # the second lesson would have to go into lunch
        (1, 1, True),  # the first lesson would need a period before period 1
        (1, 2, False),  # the first lesson can still go into period 1
    ],
)
def test_partly_placed_block_is_flagged_only_if_it_cannot_be_completed(
    client: TestClient, db_session: Session, lesson_index: int, period: int, flagged: bool
) -> None:
    """One lesson of block 1 alone on Monday (the other has no row): the
    block is wrong only if no placement of the missing lesson could make
    it right where it is."""
    world = _world(db_session)
    world.place(world.science[lesson_index], 1, period)
    world.place(world.science[2], 2, 1)

    types = {v["type"] for v in _block_violations(_check(client, world))}

    assert types == ({"BLOCK_NOT_CONSECUTIVE"} if flagged else set())


def test_row_without_teacher_is_not_a_second_teacher(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.place(world.science[0], 1, 1)
    world.place(world.science[1], 1, 2, no_teacher=True)
    world.place(world.science[2], 2, 1)
    _place_english(world)

    types = {v["type"] for v in _check(client, world)["violations"]}

    assert types == {"INCOMPLETE_SCHEDULE_ROW"}


# --- Lessons in no block ---


def test_lessons_without_blocks_are_not_affected(
    client: TestClient, db_session: Session
) -> None:
    """English (no pattern): both lessons on the same day, apart, by two
    teachers -- nothing a block rule would allow, and nothing reported."""
    world = _world(db_session)
    _place_valid_science(world)
    world.place(world.english[0], 3, 1)
    world.place(world.english[1], 3, 5, world.t2)

    assert _check(client, world)["violations"] == []


# --- Every endpoint built on the check agrees with GET /check ---


def _broken_world(db: Session) -> tuple[World, list[Schedule]]:
    """Block 1 across lunch (broken), block 2 on Tuesday, English on
    Wednesday -- so moves and swaps can both fix and break block rules."""
    world = _world(db)
    rows = [
        world.place(world.science[0], 1, 2),
        world.place(world.science[1], 1, 4),
        world.place(world.science[2], 2, 1),
        *_place_english(world),
    ]
    return world, rows


def _after_saving(client: TestClient, world: World, response: Any) -> dict:
    """The /check of the version after a change was really saved."""
    _ok(response)
    return _check(client, world)


def test_move_and_swap_previews_match_check_after_saving(
    client: TestClient, db_session: Session
) -> None:
    world, rows = _broken_world(db_session)
    # Task 89 rewrote these steps: a lesson of a block now moves with its
    # whole block, so a move can no longer split one. One after another,
    # each saved before the next: block 2 (one lesson) to Monday period 5
    # (block 1 still across lunch, now also on block 2's day), swapped
    # with English's first lesson (Wednesday), then block 1 moved whole to
    # Tuesday 4-5 by its second lesson.
    cases = [
        lambda dry: _move(client, world.version.id, rows[2].id, world.slot(1, 5), dry_run=dry),
        lambda dry: _swap(client, world.version.id, rows[2].id, rows[3].id, dry_run=dry),
        lambda dry: _move(client, world.version.id, rows[1].id, world.slot(2, 5), dry_run=dry),
    ]
    seen: set[str] = set()
    for case in cases:
        before = _check(client, world)
        preview = _ok(case(True))["check"]
        assert _check(client, world) == before  # the preview saved nothing
        saved = _after_saving(client, world, case(False))
        assert preview == saved
        seen |= {v["type"] for v in _block_violations(saved)}

    assert seen == BLOCK_TYPES
    assert _block_violations(_check(client, world)) == []


def test_reassign_preview_matches_check_after_saving(
    client: TestClient, db_session: Session
) -> None:
    world, _ = _broken_world(db_session)
    body = {
        "class_subject_requirement_id": world.science_requirement.id,
        "new_teacher_id": world.t2.id,
    }

    preview = _ok(
        client.post(f"{URL}/{world.version.id}/reassign-teacher", json={**body, "dry_run": True})
    )["check"]
    saved = _after_saving(
        client, world, client.post(f"{URL}/{world.version.id}/reassign-teacher", json=body)
    )

    assert preview == saved
    assert {v["type"] for v in _block_violations(saved)} == {"BLOCK_NOT_CONSECUTIVE"}


def test_move_candidates_match_check_and_previews(
    client: TestClient, db_session: Session
) -> None:
    world, rows = _broken_world(db_session)
    compared = 0

    for row in rows[:3]:
        data = _ok(_candidates(client, world.version.id, row.id))
        assert data["baseline"] == _check(client, world)
        for candidate in data["candidates"]:
            if candidate["available"]:
                preview = _ok(
                    _move(client, world.version.id, row.id, candidate["time_slot_id"], dry_run=True)
                )
                assert candidate["move"] == preview["check"], (row.id, candidate["time_slot_id"])
                compared += 1
            for swap in candidate["swaps"]:
                preview = _ok(
                    _swap(client, world.version.id, row.id, swap["swap_with_schedule_id"], dry_run=True)
                )
                assert swap["check"] == preview["check"]

    assert compared > 0
    # Task 89 rewrote this part (a move can no longer split a block):
    # moving block 2 (one lesson) next to block 1 on Monday leaves block 1
    # broken -- with the same identity key as before the move -- and adds
    # BLOCK_SAME_DAY.
    single = _by_slot(_ok(_candidates(client, world.version.id, rows[2].id)))
    assert single[world.slot(1, LUNCH)]["available"] is False
    keys_before = {v["identity_key"] for v in _block_violations(_check(client, world))}
    keys_after = {v["identity_key"] for v in _block_violations(single[world.slot(1, 5)]["move"])}
    requirement_id = world.science_requirement.id
    assert keys_before == {f"BLOCK_NOT_CONSECUTIVE:{requirement_id}:1"}
    assert keys_after == keys_before | {f"BLOCK_SAME_DAY:{requirement_id}:1,2"}


@pytest.mark.parametrize("weekday", [1, 3])
def test_same_day_key_does_not_depend_on_the_day(
    client: TestClient, db_session: Session, weekday: int
) -> None:
    world = _world(db_session)
    world.place(world.science[0], weekday, 1)
    world.place(world.science[1], weekday, 2)
    world.place(world.science[2], weekday, 5)

    keys = {v["identity_key"] for v in _block_violations(_check(client, world))}

    assert keys == {f"BLOCK_SAME_DAY:{world.science_requirement.id}:1,2"}


def test_schedule_ids_point_at_the_rows(client: TestClient, db_session: Session) -> None:
    world, _ = _broken_world(db_session)

    for violation in _check(client, world)["violations"]:
        row = db_session.scalars(
            select(Schedule).where(Schedule.id == violation["schedule_id"])
        ).one()
        assert row.lesson_id == violation["lesson_id"]
