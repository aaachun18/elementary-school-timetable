"""Which room run-scheduler gives each lesson. A lesson with no special
room is taught in the class's own room (原班上課), which is no school room
at all: it gets no room and takes part in no room conflict (classes have
no homeroom room). A requirement's required special room is held fixed --
its only room candidate -- and the pre-checks report the room problems no
search could solve.

Test data is written straight to the database through db_session; the
lessons come from the real generate-lessons endpoint (lesson blocks
included), the timetable from the real run-scheduler endpoint.
"""

from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear, Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class, Grade
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.models.time_slot import TimeSlot
from tests.conftest import (
    enroll_in_semester,
    get_test_school_id,
    make_record,
    next_free_grade_level,
    time_slot_at,
)

URL = "/api/v1/schedule-versions"


@dataclass
class World:
    """Two classes c1, c2, each needing 國語 2, 數學 2 (one block of 2) and
    自然 (science_periods, default 1) in the required room lab. The school
    also has rooms r1, r2 nobody requires. Teachers tA and tB take part in
    the semester."""

    db: Session
    version: ScheduleVersion
    c1: Class
    c2: Class
    r1: Room
    r2: Room
    lab: Room
    science: dict[str, ClassSubjectRequirement]
    requirements: dict[tuple[str, str], ClassSubjectRequirement]
    slots: dict[tuple[int, int], TimeSlot]

    def generate(self, client: TestClient) -> None:
        response = client.post(f"{URL}/{self.version.id}/generate-lessons")
        assert response.status_code == 200, response.json()

    def run(self, client: TestClient) -> dict:
        self.generate(client)
        response = client.post(f"{URL}/{self.version.id}/run-scheduler")
        data: dict = response.json()
        data["status_code"] = response.status_code
        return data

    def rows(self, class_: Class, subject: str) -> list[Schedule]:
        requirement = self.requirements[(class_.name, subject)]
        self.db.expire_all()
        return list(
            self.db.scalars(
                select(Schedule)
                .join(Lesson, Schedule.lesson_id == Lesson.id)
                .where(
                    Schedule.schedule_version_id == self.version.id,
                    Lesson.class_subject_requirement_id == requirement.id,
                )
                .order_by(Lesson.block_seq, Lesson.sequence_number)
            ).all()
        )

    def lessons(self, class_: Class, subject: str) -> list[Lesson]:
        requirement = self.requirements[(class_.name, subject)]
        return list(
            self.db.scalars(
                select(Lesson)
                .where(Lesson.class_subject_requirement_id == requirement.id)
                .order_by(Lesson.sequence_number)
            ).all()
        )


def _world(
    db: Session, *, days: int = 3, periods: int = 4, science_periods: int = 1
) -> World:
    year = AcademicYear(school_id=get_test_school_id(db), year=9201, is_active=True)
    db.add(year)
    db.flush()
    semester = Semester(academic_year_id=year.id, number=1, is_active=True)
    grade = Grade(school_id=get_test_school_id(db), name="Grade 9201", level=next_free_grade_level(db))
    db.add_all([semester, grade])
    db.flush()
    slots = {
        (weekday, period): time_slot_at(db, weekday, period, is_teaching_period=True)
        for weekday in range(1, days + 1)
        for period in range(1, periods + 1)
    }
    r1 = Room(school_id=get_test_school_id(db), name="四甲教室", is_active=True)
    r2 = Room(school_id=get_test_school_id(db), name="四乙教室", is_active=True)
    lab = Room(school_id=get_test_school_id(db), name="自然教室一", is_active=True)
    subjects = {name: Subject(school_id=get_test_school_id(db), name=name, is_active=True) for name in ("國語", "數學", "自然")}
    t_a = Teacher(school_id=get_test_school_id(db), name="甲老師", is_active=True, min_weekly_periods=0, max_weekly_periods=30)
    t_b = Teacher(school_id=get_test_school_id(db), name="乙老師", is_active=True, min_weekly_periods=0, max_weekly_periods=30)
    db.add_all([*slots.values(), r1, r2, lab, *subjects.values(), t_a, t_b])
    db.flush()
    c1 = Class(grade_id=grade.id, name="四年甲班")
    c2 = Class(grade_id=grade.id, name="四年乙班")
    db.add_all([c1, c2])
    db.flush()
    version = make_record(db, semester.id)
    for teacher in (t_a, t_b):
        enroll_in_semester(db, version.id, teacher)
    requirements: dict[tuple[str, str], ClassSubjectRequirement] = {}
    for class_ in (c1, c2):
        for name, periods_, pattern, room_id in (
            ("國語", 2, None, None),
            ("數學", 2, "2", None),
            ("自然", science_periods, None, lab.id),
        ):
            requirements[(class_.name, name)] = ClassSubjectRequirement(
                schedule_version_id=version.id,
                class_id=class_.id,
                subject_id=subjects[name].id,
                weekly_periods=periods_,
                lesson_pattern=pattern,
                required_room_id=room_id,
            )
    db.add_all(requirements.values())
    db.commit()
    science = {class_.name: requirements[(class_.name, "自然")] for class_ in (c1, c2)}
    return World(db, version, c1, c2, r1, r2, lab, science, requirements, slots)


def _check(client: TestClient, world: World) -> dict:
    response = client.get(f"{URL}/{world.version.id}/check")
    assert response.status_code == 200
    data: dict = response.json()
    return data


def _static(data: dict, violation_type: str) -> list[dict]:
    assert data["status_code"] == 422, data
    assert data["failure_type"] == "STATIC_CHECK_FAILED"
    return [v for v in data["post_hoc_violations"] if v["type"] == violation_type]


# --- Which room each lesson gets ---


def test_lessons_without_a_special_room_get_no_room(
    client: TestClient, db_session: Session
) -> None:
    """原班上課: no room, even though the school has unused rooms."""
    world = _world(db_session)

    data = world.run(client)

    assert data["status_code"] == 200, data
    for class_ in (world.c1, world.c2):
        for subject in ("國語", "數學"):
            assert {row.room_id for row in world.rows(class_, subject)} == {None}
        # A required room: that room.
        assert {row.room_id for row in world.rows(class_, "自然")} == {world.lab.id}
    assert _check(client, world)["violations"] == []


def test_lesson_block_without_a_room_is_still_consecutive(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)

    assert world.run(client)["status_code"] == 200

    first, second = world.rows(world.c1, "數學")
    assert first.room_id is None and second.room_id is None
    position = {slot.id: (slot.weekday, slot.period) for slot in world.slots.values()}
    (day1, period1), (day2, period2) = position[first.time_slot_id], position[second.time_slot_id]  # type: ignore[index]
    assert (day1, period1 + 1) == (day2, period2)


def test_fixed_lesson_without_a_room_stays_at_its_fixed_slot(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.generate(client)
    fixed_slot = world.slots[(2, 3)].id
    lesson = world.lessons(world.c1, "國語")[0]
    lesson.fixed_time_slot_id = fixed_slot
    db_session.commit()

    response = client.post(f"{URL}/{world.version.id}/run-scheduler")

    assert response.status_code == 200, response.json()
    row = next(row for row in world.rows(world.c1, "國語") if row.lesson_id == lesson.id)
    assert (row.time_slot_id, row.room_id) == (fixed_slot, None)
    assert _check(client, world)["violations"] == []  # no FIXED_TIME_SLOT_MISMATCH


# --- Rooms and room conflicts ---


def test_shared_required_room_never_holds_two_lessons_at_once(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session, science_periods=3)

    assert world.run(client)["status_code"] == 200

    rows = [row for c in (world.c1, world.c2) for row in world.rows(c, "自然")]
    assert {row.room_id for row in rows} == {world.lab.id}
    assert len({row.time_slot_id for row in rows}) == len(rows) == 6
    assert _check(client, world)["violations"] == []


def test_classes_without_rooms_can_be_at_the_same_time(
    client: TestClient, db_session: Session
) -> None:
    """No room means no room conflict: both classes' 國語 fixed to one
    slot is fine."""
    world = _world(db_session)
    world.generate(client)
    slot = world.slots[(1, 1)].id
    for class_ in (world.c1, world.c2):
        world.lessons(class_, "國語")[0].fixed_time_slot_id = slot
    db_session.commit()

    response = client.post(f"{URL}/{world.version.id}/run-scheduler")

    assert response.status_code == 200, response.json()
    assert _check(client, world)["violations"] == []


def test_shared_required_room_with_too_many_lessons_is_reported_before_searching(
    client: TestClient, db_session: Session
) -> None:
    """8 lessons only the lab can hold, 6 teaching periods."""
    world = _world(db_session, days=2, periods=3, science_periods=4)

    data = world.run(client)

    [violation] = _static(data, "STATIC_ROOM_OVERBOOKED")
    assert violation["room_id"] == world.lab.id
    assert violation["message"] == "教室「自然教室一」要上 8 堂課，但一週只有 6 個教學時段"
    assert violation["suggested_action"]


def test_shared_required_room_with_lessons_fixed_to_one_slot_is_reported(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.generate(client)
    slot = world.slots[(1, 1)].id
    fixed = [world.lessons(world.c1, "自然")[0], world.lessons(world.c2, "自然")[0]]
    for lesson in fixed:
        lesson.fixed_time_slot_id = slot
    db_session.commit()

    response = client.post(f"{URL}/{world.version.id}/run-scheduler")
    data = {**response.json(), "status_code": response.status_code}

    clashes = _static(data, "STATIC_FIXED_SLOT_ROOM_CLASH")
    assert sorted(v["lesson_id"] for v in clashes) == sorted(lesson.id for lesson in fixed)
    assert {(v["room_id"], v["time_slot_id"]) for v in clashes} == {(world.lab.id, slot)}
    assert clashes[0]["message"] == (
        "多個班級都在「自然教室一」上課，而且都有課固定在同一個時段，這間教室同一時段只能上一堂課"
    )


def test_one_class_with_two_lessons_fixed_to_one_slot_is_a_class_clash_only(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.generate(client)
    for lesson in world.lessons(world.c1, "國語"):
        lesson.fixed_time_slot_id = world.slots[(1, 1)].id
    db_session.commit()

    response = client.post(f"{URL}/{world.version.id}/run-scheduler")
    data = {**response.json(), "status_code": response.status_code}

    assert _static(data, "STATIC_FIXED_SLOT_ROOM_CLASH") == []
    assert len(_static(data, "STATIC_FIXED_SLOT_CLASS_CLASH")) == 2


def test_inactive_unrequired_room_changes_nothing(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.r1.is_active = False
    db_session.commit()

    assert world.run(client)["status_code"] == 200


def test_inactive_required_room_is_reported_before_searching(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.lab.is_active = False
    db_session.commit()

    data = world.run(client)

    inactive = _static(data, "STATIC_INACTIVE_ENTITY_CONFLICT")
    assert {v["class_subject_requirement_id"] for v in inactive} == {
        world.science["四年甲班"].id,
        world.science["四年乙班"].id,
    }
    assert {v["room_id"] for v in inactive} == {world.lab.id}
