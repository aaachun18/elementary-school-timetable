"""Task 92B: run-scheduler holds a lesson of no room type (原班上課) in its
class's homeroom -- fixed, the only room candidate (decision 29) -- and the
pre-checks report the room problems no search could solve.

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
from app.models.teacher import Teacher, TeacherSubject
from app.models.time_slot import TimeSlot

URL = "/api/v1/schedule-versions"


@dataclass
class World:
    """Two classes, c1 with homeroom r1 and c2 with none, each needing
    國語 2, 數學 2 (one block of 2) and 自然 1 in a 自然教室 (lab). tA
    teaches 國語 and 數學, tB 自然."""

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


def _world(db: Session, *, days: int = 3, periods: int = 4) -> World:
    year = AcademicYear(year=9201, is_active=True)
    db.add(year)
    db.flush()
    semester = Semester(academic_year_id=year.id, number=1, is_active=True)
    grade = Grade(name="Grade 9201", level=9201)
    db.add_all([semester, grade])
    db.flush()
    slots = {
        (weekday, period): TimeSlot(weekday=weekday, period=period, is_teaching_period=True)
        for weekday in range(1, days + 1)
        for period in range(1, periods + 1)
    }
    r1 = Room(name="四甲教室", room_type="普通教室", is_active=True)
    r2 = Room(name="四乙教室", room_type="普通教室", is_active=True)
    lab = Room(name="自然教室一", room_type="自然教室", is_active=True)
    subjects = {name: Subject(name=name, is_active=True) for name in ("國語", "數學", "自然")}
    t_a = Teacher(name="甲老師", is_active=True, min_weekly_periods=0, max_weekly_periods=30)
    t_b = Teacher(name="乙老師", is_active=True, min_weekly_periods=0, max_weekly_periods=30)
    db.add_all([*slots.values(), r1, r2, lab, *subjects.values(), t_a, t_b])
    db.flush()
    c1 = Class(grade_id=grade.id, name="四年甲班", is_active=True, homeroom_room_id=r1.id)
    c2 = Class(grade_id=grade.id, name="四年乙班", is_active=True)
    db.add_all([c1, c2])
    db.add_all(
        [TeacherSubject(teacher_id=t_a.id, subject_id=subjects[name].id) for name in ("國語", "數學")]
        + [TeacherSubject(teacher_id=t_b.id, subject_id=subjects["自然"].id)]
    )
    db.flush()
    requirements: dict[tuple[str, str], ClassSubjectRequirement] = {}
    for class_ in (c1, c2):
        for name, periods_, pattern, room_type in (
            ("國語", 2, None, None),
            ("數學", 2, "2", None),
            ("自然", 1, None, "自然教室"),
        ):
            requirements[(class_.name, name)] = ClassSubjectRequirement(
                semester_id=semester.id,
                class_id=class_.id,
                subject_id=subjects[name].id,
                weekly_periods=periods_,
                lesson_pattern=pattern,
                required_room_type=room_type,
            )
    db.add_all(requirements.values())
    version = ScheduleVersion(semester_id=semester.id, version_number=1, status="DRAFT")
    db.add(version)
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


def test_homeroom_class_gets_its_homeroom_and_others_stay_empty(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)

    data = world.run(client)

    assert data["status_code"] == 200, data
    for subject in ("國語", "數學"):
        assert {row.room_id for row in world.rows(world.c1, subject)} == {world.r1.id}
        # No homeroom: exactly as before Task 92B.
        assert {row.room_id for row in world.rows(world.c2, subject)} == {None}
    # A room type: a room of that type, never the homeroom.
    for class_ in (world.c1, world.c2):
        assert {row.room_id for row in world.rows(class_, "自然")} == {world.lab.id}
    assert _check(client, world)["violations"] == []


def test_lesson_block_is_held_in_one_homeroom(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    assert world.run(client)["status_code"] == 200

    first, second = world.rows(world.c1, "數學")
    assert first.room_id == second.room_id == world.r1.id
    position = {slot.id: (slot.weekday, slot.period) for slot in world.slots.values()}
    (day1, period1), (day2, period2) = position[first.time_slot_id], position[second.time_slot_id]  # type: ignore[index]
    assert (day1, period1 + 1) == (day2, period2)


def test_fixed_lesson_is_held_in_the_homeroom_at_its_fixed_slot(
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
    assert (row.time_slot_id, row.room_id) == (fixed_slot, world.r1.id)
    assert _check(client, world)["violations"] == []  # no FIXED_TIME_SLOT_MISMATCH


# --- Two classes sharing one homeroom: H3 keeps them apart ---


def test_shared_homeroom_never_holds_two_lessons_at_once(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.c2.homeroom_room_id = world.r1.id
    db_session.commit()

    assert world.run(client)["status_code"] == 200

    rows = [row for c in (world.c1, world.c2) for s in ("國語", "數學") for row in world.rows(c, s)]
    assert {row.room_id for row in rows} == {world.r1.id}
    assert len({row.time_slot_id for row in rows}) == len(rows) == 8
    assert _check(client, world)["violations"] == []


def test_shared_homeroom_with_too_many_lessons_is_reported_before_searching(
    client: TestClient, db_session: Session
) -> None:
    """8 lessons only the shared homeroom can hold, 6 teaching periods."""
    world = _world(db_session, days=2, periods=3)
    world.c2.homeroom_room_id = world.r1.id
    db_session.commit()

    data = world.run(client)

    [violation] = _static(data, "STATIC_HOMEROOM_OVERBOOKED")
    assert violation["room_id"] == world.r1.id
    assert violation["message"] == "導師教室「四甲教室」（四年甲班、四年乙班）要上 8 堂課，但一週只有 6 個教學時段"
    assert violation["suggested_action"]


def test_shared_homeroom_with_lessons_fixed_to_one_slot_is_reported(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.c2.homeroom_room_id = world.r1.id
    db_session.commit()
    world.generate(client)
    slot = world.slots[(1, 1)].id
    fixed = [world.lessons(world.c1, "國語")[0], world.lessons(world.c2, "國語")[0]]
    for lesson in fixed:
        lesson.fixed_time_slot_id = slot
    db_session.commit()

    response = client.post(f"{URL}/{world.version.id}/run-scheduler")
    data = {**response.json(), "status_code": response.status_code}

    clashes = _static(data, "STATIC_FIXED_SLOT_HOMEROOM_CLASH")
    assert sorted(v["lesson_id"] for v in clashes) == sorted(lesson.id for lesson in fixed)
    assert {(v["room_id"], v["time_slot_id"]) for v in clashes} == {(world.r1.id, slot)}
    assert clashes[0]["message"] == (
        "四年甲班、四年乙班共用導師教室「四甲教室」，而且都有課固定在同一個時段，這間教室同一時段只能上一堂課"
    )


def test_one_class_alone_with_its_homeroom_is_no_homeroom_clash(
    client: TestClient, db_session: Session
) -> None:
    """Two lessons of one class fixed to one slot are a class clash, not
    also a homeroom one."""
    world = _world(db_session)
    world.generate(client)
    for lesson in world.lessons(world.c1, "國語"):
        lesson.fixed_time_slot_id = world.slots[(1, 1)].id
    db_session.commit()

    response = client.post(f"{URL}/{world.version.id}/run-scheduler")
    data = {**response.json(), "status_code": response.status_code}

    assert _static(data, "STATIC_FIXED_SLOT_HOMEROOM_CLASH") == []
    assert len(_static(data, "STATIC_FIXED_SLOT_CLASS_CLASH")) == 2


def test_inactive_homeroom_is_reported_before_searching(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.r1.is_active = False
    db_session.commit()

    data = world.run(client)

    inactive = _static(data, "STATIC_INACTIVE_ENTITY_CONFLICT")
    assert {v["class_subject_requirement_id"] for v in inactive} == {
        world.requirements[("四年甲班", "國語")].id,
        world.requirements[("四年甲班", "數學")].id,
    }
    assert {v["room_id"] for v in inactive} == {world.r1.id}


# --- Room types are matched as the exact same string ---


def test_room_type_matching_no_room_is_reported_with_class_and_subject(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.science["四年甲班"].required_room_type = "自然教室 "  # trailing space
    world.science["四年乙班"].required_room_type = "自然"
    db_session.commit()

    data = world.run(client)

    found = {v["class_subject_requirement_id"]: v for v in _static(data, "STATIC_ROOM_TYPE_NOT_FOUND")}
    assert set(found) == {world.science["四年甲班"].id, world.science["四年乙班"].id}
    assert found[world.science["四年甲班"].id]["message"] == "四年甲班的自然指定的教室類型「自然教室 」找不到任何可用的教室"
    assert found[world.science["四年乙班"].id]["message"] == "四年乙班的自然指定的教室類型「自然」找不到任何可用的教室"
    assert found[world.science["四年乙班"].id]["class_id"] == world.c2.id
    assert all(v["suggested_action"] for v in found.values())


def test_room_type_with_only_inactive_rooms_is_reported(
    client: TestClient, db_session: Session
) -> None:
    world = _world(db_session)
    world.lab.is_active = False
    db_session.commit()

    data = world.run(client)

    assert len(_static(data, "STATIC_ROOM_TYPE_NOT_FOUND")) == 2


def test_room_type_of_the_same_string_is_found(client: TestClient, db_session: Session) -> None:
    world = _world(db_session)

    data = world.run(client)

    assert data["status_code"] == 200
    assert {row.room_id for row in world.rows(world.c2, "自然")} == {world.lab.id}
