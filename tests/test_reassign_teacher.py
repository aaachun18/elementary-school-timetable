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
from app.models.semester_teacher import SemesterTeacher, SemesterTeacherUnavailability
from app.models.teacher import Teacher
from app.models.time_slot import TimeSlot
from app.services import schedule_check, teacher_reassignment
from tests.conftest import (
    enroll_in_semester,
    get_test_school_id,
    make_record,
    mark_status_in_db,
    next_free_grade_level,
    time_slot_at,
)

# Task 63: POST /api/v1/schedule-versions/{id}/reassign-teacher. Test data
# is written straight to the database through db_session (the same session
# the client fixtures' requests use). v3: 換教師 only works in a manual
# edit's working copy of a copied timetable -- the Builder's record is such
# a working copy by default.


# --- Builders ---


class Builder:
    """Small helpers for writing one semester's timetable straight to the
    database. Every helper commits, so each returned id is final.

    v3: settings belong to a 排課紀錄, so the builder starts with one record
    of its semester (`self.record`): teachers take part in it, and
    version() hands it out first -- in `status` (default: EDITING, the
    working copy every manual adjustment runs in, editing a COPIED record
    so 換教師 is allowed too)."""

    def __init__(self, db: Session, year: int = 6001, *, status: str = "EDITING") -> None:
        self.db = db
        self.status = status
        self._record_handed_out = False
        self.academic_year = AcademicYear(school_id=get_test_school_id(db), year=year, is_active=True)
        db.add(self.academic_year)
        db.flush()
        self.semester = self.semester_in_year(number=1)
        self.grade = Grade(school_id=get_test_school_id(db), name=f"Grade {year}", level=next_free_grade_level(db))
        db.add(self.grade)
        db.flush()
        self.slots = [
            time_slot_at(db, 1, period, is_teaching_period=True)
            for period in range(1, 7)
        ]
        db.add_all(self.slots)
        db.commit()
        self.record = make_record(db, self.semester.id)

    def semester_in_year(self, number: int) -> Semester:
        semester = Semester(
            academic_year_id=self.academic_year.id, number=number, is_active=True
        )
        self.db.add(semester)
        self.db.commit()
        return semester

    def subject(self, name: str) -> Subject:
        subject = Subject(school_id=get_test_school_id(self.db), name=name, is_active=True)
        self.db.add(subject)
        self.db.commit()
        return subject

    def teacher(
        self, name: str, max_weekly_periods: int = 20, *, takes_part: bool = True
    ) -> Teacher:
        """Task 98: a teacher of the school, taking part in the builder's
        record (unless takes_part=False) with this weekly maximum."""
        teacher = Teacher(
            school_id=get_test_school_id(self.db),
            name=name,
            is_active=True,
            min_weekly_periods=0,
            max_weekly_periods=max_weekly_periods,
        )
        self.db.add(teacher)
        self.db.commit()
        if takes_part:
            enroll_in_semester(self.db, self.record.id, teacher)
        return teacher

    def semester_teacher(self, teacher: Teacher) -> SemesterTeacher:
        """The teacher's settings in the builder's record."""
        row = self.db.scalars(
            select(SemesterTeacher).where(
                SemesterTeacher.schedule_version_id == self.record.id,
                SemesterTeacher.teacher_id == teacher.id,
            )
        ).one()
        return row

    def make_unavailable(self, teacher: Teacher, time_slot_id: int) -> None:
        """Task 98: unavailable in the builder's record."""
        self.db.add(
            SemesterTeacherUnavailability(
                semester_teacher_id=self.semester_teacher(teacher).id,
                time_slot_id=time_slot_id,
            )
        )
        self.db.commit()

    def class_(self, name: str) -> Class:
        class_ = Class(grade_id=self.grade.id, name=name)
        self.db.add(class_)
        self.db.commit()
        return class_

    def version(
        self, semester: Semester | None = None, *, status: str | None = None
    ) -> ScheduleVersion:
        """The builder's record the first time (for its own semester),
        another record of `semester` after that -- in `status` (default:
        the builder's)."""
        status = status or self.status
        if semester is None and not self._record_handed_out:
            self._record_handed_out = True
            version = self.record
        else:
            version = make_record(self.db, (semester or self.semester).id)
        mark_status_in_db(self.db, version.id, status, source_status="COPIED")
        self.db.refresh(version)
        return version

    def course(
        self,
        version: ScheduleVersion,
        class_: Class,
        subject: Subject,
        teacher: Teacher | None,
        slot_indexes: list[int],
        *,
        required_teacher: Teacher | None = None,
        unscheduled_periods: int = 0,
    ) -> ClassSubjectRequirement:
        """One requirement with len(slot_indexes) + unscheduled_periods
        Lessons; the first len(slot_indexes) are placed in `version`,
        taught by `teacher`, in those time slots."""
        requirement = ClassSubjectRequirement(
            schedule_version_id=version.id,
            class_id=class_.id,
            subject_id=subject.id,
            weekly_periods=len(slot_indexes) + unscheduled_periods,
            required_teacher_id=required_teacher.id if required_teacher else None,
        )
        self.db.add(requirement)
        self.db.flush()
        lessons = [
            Lesson(class_subject_requirement_id=requirement.id, sequence_number=number)
            for number in range(1, requirement.weekly_periods + 1)
        ]
        self.db.add_all(lessons)
        self.db.flush()
        self.db.add_all(
            [
                Schedule(
                    schedule_version_id=version.id,
                    lesson_id=lesson.id,
                    teacher_id=teacher.id if teacher else None,
                    time_slot_id=self.slots[slot_index].id,
                    room_id=None,
                )
                for lesson, slot_index in zip(lessons, slot_indexes)
            ]
        )
        self.db.commit()
        return requirement


@dataclass
class World:
    """One working copy (EDITING, of a COPIED record), valid as built:
    - class 1 English (2 periods, slots 0-1) by old_teacher, who is also
      its required teacher;
    - class 2 Science (1 period, slot 2) by new_teacher.
    Both teachers are qualified for both subjects."""

    builder: Builder
    version: ScheduleVersion
    old_teacher: Teacher
    new_teacher: Teacher
    english: Subject
    science: Subject
    english_requirement: ClassSubjectRequirement
    science_requirement: ClassSubjectRequirement


def _build_world(db: Session, *, english_required_teacher: bool = True) -> World:
    builder = Builder(db)
    english = builder.subject("英文")
    science = builder.subject("自然")
    old_teacher = builder.teacher("舊老師")
    new_teacher = builder.teacher("新老師")
    class_1 = builder.class_("一年甲班")
    class_2 = builder.class_("一年乙班")
    version = builder.version()
    english_requirement = builder.course(
        version,
        class_1,
        english,
        old_teacher,
        [0, 1],
        required_teacher=old_teacher if english_required_teacher else None,
    )
    science_requirement = builder.course(version, class_2, science, new_teacher, [2])
    return World(
        builder=builder,
        version=version,
        old_teacher=old_teacher,
        new_teacher=new_teacher,
        english=english,
        science=science,
        english_requirement=english_requirement,
        science_requirement=science_requirement,
    )


# --- Request / inspection helpers ---


def _reassign(
    client: TestClient,
    version_id: int,
    requirement_id: int,
    teacher_id: int,
    *,
    dry_run: bool | None = None,
) -> Any:
    body: dict[str, Any] = {
        "class_subject_requirement_id": requirement_id,
        "new_teacher_id": teacher_id,
    }
    if dry_run is not None:
        body["dry_run"] = dry_run
    return client.post(f"/api/v1/schedule-versions/{version_id}/reassign-teacher", json=body)


def _reassign_ok(
    client: TestClient, version_id: int, requirement_id: int, teacher_id: int, **kwargs: Any
) -> dict:
    response = _reassign(client, version_id, requirement_id, teacher_id, **kwargs)
    assert response.status_code == 200, response.json()
    data: dict = response.json()
    return data


def _violation_types(data: dict) -> set[str]:
    return {v["type"] for v in data["check"]["violations"]}


def _rows_of(db: Session, version_id: int, requirement_id: int) -> list[Schedule]:
    db.expire_all()
    return list(
        db.scalars(
            select(Schedule)
            .join(Lesson, Schedule.lesson_id == Lesson.id)
            .where(
                Schedule.schedule_version_id == version_id,
                Lesson.class_subject_requirement_id == requirement_id,
            )
            .order_by(Schedule.id)
        ).all()
    )


def _required_teacher_id(db: Session, requirement_id: int) -> int | None:
    db.expire_all()
    requirement = db.get(ClassSubjectRequirement, requirement_id)
    assert requirement is not None
    return requirement.required_teacher_id


def _snapshot(db: Session) -> list[tuple[object, ...]]:
    """Every column of every requirement and Schedule row."""
    db.expire_all()
    snapshot: list[tuple[object, ...]] = []
    for model in (ClassSubjectRequirement, Schedule, ScheduleVersion):
        columns = list(model.__table__.columns.keys())
        for row in db.scalars(select(model).order_by(model.id)).all():
            snapshot.append((model.__name__, *(getattr(row, c) for c in columns)))
    return snapshot


# --- Basic behaviour ---


def test_reassign_updates_requirement_and_this_versions_rows(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    science_before = [
        (r.id, r.teacher_id, r.time_slot_id)
        for r in _rows_of(db_session, world.version.id, world.science_requirement.id)
    ]

    data = _reassign_ok(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id
    )

    assert data["schedule_version_id"] == world.version.id
    assert data["class_subject_requirement_id"] == world.english_requirement.id
    assert data["previous_teacher_id"] == world.old_teacher.id
    assert data["new_teacher_id"] == world.new_teacher.id
    assert data["updated_schedule_row_count"] == 2
    assert data["dry_run"] is False
    assert _required_teacher_id(db_session, world.english_requirement.id) == world.new_teacher.id
    english_rows = _rows_of(db_session, world.version.id, world.english_requirement.id)
    assert [r.teacher_id for r in english_rows] == [world.new_teacher.id] * 2
    # Only teachers change: the lessons stay in their time slots.
    assert [r.time_slot_id for r in english_rows] == [
        world.builder.slots[0].id,
        world.builder.slots[1].id,
    ]
    assert [
        (r.id, r.teacher_id, r.time_slot_id)
        for r in _rows_of(db_session, world.version.id, world.science_requirement.id)
    ] == science_before


def test_reassign_sets_required_teacher_when_it_was_empty(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session, english_required_teacher=False)
    assert _required_teacher_id(db_session, world.english_requirement.id) is None

    data = _reassign_ok(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id
    )

    assert _required_teacher_id(db_session, world.english_requirement.id) == world.new_teacher.id
    # The timetable showed old_teacher on every row.
    assert data["previous_teacher_id"] == world.old_teacher.id


def test_reassign_to_current_teacher_is_a_no_op(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    before = _snapshot(db_session)

    data = _reassign_ok(
        client, world.version.id, world.english_requirement.id, world.old_teacher.id
    )

    assert data["previous_teacher_id"] == world.old_teacher.id
    # Task 64: only rows that actually change are counted.
    assert data["updated_schedule_row_count"] == 0
    assert data["check"]["is_valid"] is True
    assert _snapshot(db_session) == before


def test_reassign_counts_only_rows_that_change(
    client: TestClient, db_session: Session
) -> None:
    # Task 64: one of English's two rows already has the new teacher.
    world = _build_world(db_session)
    first_row = _rows_of(db_session, world.version.id, world.english_requirement.id)[0]
    first_row.teacher_id = world.new_teacher.id
    db_session.commit()

    dry = _reassign_ok(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id, dry_run=True
    )
    real = _reassign_ok(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id
    )

    assert dry["updated_schedule_row_count"] == 1
    assert real["updated_schedule_row_count"] == 1
    assert {
        r.teacher_id
        for r in _rows_of(db_session, world.version.id, world.english_requirement.id)
    } == {world.new_teacher.id}


def test_reassign_requirement_without_schedule_rows(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    class_3 = world.builder.class_("一年丙班")
    unscheduled = world.builder.course(
        world.version, class_3, world.english, None, [], unscheduled_periods=1
    )

    data = _reassign_ok(client, world.version.id, unscheduled.id, world.new_teacher.id)

    assert data["updated_schedule_row_count"] == 0
    assert data["previous_teacher_id"] is None
    assert _required_teacher_id(db_session, unscheduled.id) == world.new_teacher.id


# --- The check after the change ---


def test_reassign_reports_teacher_conflict(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)
    # new_teacher's Science lesson moves to slot 0 -- where English is.
    science_row = _rows_of(db_session, world.version.id, world.science_requirement.id)[0]
    science_row.time_slot_id = world.builder.slots[0].id
    db_session.commit()

    data = _reassign_ok(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id
    )

    h1 = [v for v in data["check"]["violations"] if v["type"] == "H1_TEACHER_CONFLICT"]
    assert h1
    assert {v["teacher_id"] for v in h1} == {world.new_teacher.id}
    assert {v["time_slot_id"] for v in h1} == {world.builder.slots[0].id}


def test_reassign_reports_unavailable_slot(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)
    world.builder.make_unavailable(world.new_teacher, world.builder.slots[1].id)

    data = _reassign_ok(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id
    )

    assert "H4_TEACHER_AVAILABILITY" in _violation_types(data)


def test_reassign_reports_teacher_not_taking_part(
    client: TestClient, db_session: Session
) -> None:
    """Task 98 (was: missing qualification): not refused, but the check
    reports it -- the semester knows no weekly maximum or unavailable
    slots for such a teacher."""
    world = _build_world(db_session)
    outsider = world.builder.teacher("未參與老師", takes_part=False)

    data = _reassign_ok(
        client, world.version.id, world.english_requirement.id, outsider.id
    )

    assert "H5_TEACHER_NOT_PARTICIPATING" in _violation_types(data)


def test_reassign_reports_workload_over_limit(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    # Task 98: the semester's own maximum.
    world.builder.semester_teacher(world.new_teacher).max_weekly_periods = 2  # already teaches 1, English adds 2
    db_session.commit()

    data = _reassign_ok(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id
    )

    assert "H8_TEACHER_MAX_WORKLOAD" in _violation_types(data)


def test_reassign_without_conflict_is_valid(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)

    data = _reassign_ok(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id
    )

    assert data["check"]["is_valid"] is True
    assert data["check"]["violation_count"] == 0


# --- The school office's real sequence ---


def test_reassign_chain_after_teacher_leaves(client: TestClient, db_session: Session) -> None:
    """Teacher X (3 Science + 2 Integrated, class 1) leaves. Integrated goes
    to A -- but A teaches English to class 2 in those same slots, so A's
    English goes to C, and finally Science goes to B."""
    builder = Builder(db_session)
    science = builder.subject("自然")
    integrated = builder.subject("綜合")
    english = builder.subject("英文")
    teacher_x = builder.teacher("X 老師")
    teacher_a = builder.teacher("A 老師")
    teacher_b = builder.teacher("B 老師")
    teacher_c = builder.teacher("C 老師")
    class_1 = builder.class_("三年甲班")
    class_2 = builder.class_("三年乙班")
    version = builder.version()
    science_requirement = builder.course(version, class_1, science, teacher_x, [0, 1, 2])
    integrated_requirement = builder.course(version, class_1, integrated, teacher_x, [3, 4])
    english_requirement = builder.course(version, class_2, english, teacher_a, [3, 4])

    teacher = db_session.get(Teacher, teacher_x.id)
    assert teacher is not None
    teacher.is_active = False  # X has left
    db_session.commit()

    step_1 = _reassign_ok(client, version.id, integrated_requirement.id, teacher_a.id)
    assert "H1_TEACHER_CONFLICT" in _violation_types(step_1)

    step_2 = _reassign_ok(client, version.id, english_requirement.id, teacher_c.id)
    assert "H1_TEACHER_CONFLICT" not in _violation_types(step_2)

    step_3 = _reassign_ok(client, version.id, science_requirement.id, teacher_b.id)
    assert step_3["check"]["is_valid"] is True

    check = client.get(f"/api/v1/schedule-versions/{version.id}/check").json()
    assert check["is_valid"] is True


# --- dry_run ---


def test_dry_run_saves_nothing_but_reports_violations(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    outsider = world.builder.teacher("未參與老師", takes_part=False)
    before = _snapshot(db_session)

    data = _reassign_ok(
        client, world.version.id, world.english_requirement.id, outsider.id, dry_run=True
    )

    assert data["dry_run"] is True
    assert data["updated_schedule_row_count"] == 2
    assert "H5_TEACHER_NOT_PARTICIPATING" in _violation_types(data)
    assert _snapshot(db_session) == before


def test_only_non_dry_run_saves(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)

    _reassign_ok(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id, dry_run=True
    )
    assert _required_teacher_id(db_session, world.english_requirement.id) == world.old_teacher.id

    _reassign_ok(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id, dry_run=False
    )
    assert _required_teacher_id(db_session, world.english_requirement.id) == world.new_teacher.id
    assert {
        r.teacher_id
        for r in _rows_of(db_session, world.version.id, world.english_requirement.id)
    } == {world.new_teacher.id}


# --- Refusals: nothing may change ---


def test_reassign_missing_version_returns_404(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)
    before = _snapshot(db_session)

    response = _reassign(client, 999999, world.english_requirement.id, world.new_teacher.id)

    assert response.status_code == 404
    assert response.json()["detail"] == "ScheduleVersion not found"
    assert _snapshot(db_session) == before


def test_reassign_missing_requirement_returns_404(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    before = _snapshot(db_session)

    response = _reassign(client, world.version.id, 999999, world.new_teacher.id)

    assert response.status_code == 404
    assert response.json()["detail"] == "ClassSubjectRequirement not found"
    assert _snapshot(db_session) == before


def test_reassign_missing_teacher_returns_404(client: TestClient, db_session: Session) -> None:
    world = _build_world(db_session)
    before = _snapshot(db_session)

    response = _reassign(client, world.version.id, world.english_requirement.id, 999999)

    assert response.status_code == 404
    assert response.json()["detail"] == "Teacher not found"
    assert _snapshot(db_session) == before


def test_reassign_requirement_of_other_record_returns_409(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    other_semester = world.builder.semester_in_year(number=2)
    other_version = world.builder.version(other_semester)
    before = _snapshot(db_session)

    response = _reassign(
        client, other_version.id, world.english_requirement.id, world.new_teacher.id
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "此排課需求不屬於這筆排課紀錄"
    assert _snapshot(db_session) == before


@pytest.mark.parametrize("status", ["AUTO", "MANUAL", "COPIED"])
def test_reassign_outside_a_manual_edit_returns_409(
    client: TestClient, db_session: Session, status: str
) -> None:
    """v3: a saved timetable never changes in place -- not even a copied
    one, whose teachers change in its manual edit."""
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, status, is_published=status == "AUTO")
    before = _snapshot(db_session)

    response = _reassign(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "課表不能直接修改，請先按「手動編輯課表」"
    assert _snapshot(db_session) == before


@pytest.mark.parametrize("source_status", ["AUTO", "MANUAL"])
def test_reassign_works_in_an_edit_of_any_timetable(
    client: TestClient, db_session: Session, source_status: str
) -> None:
    """換教師 is part of every manual edit now, not only of a copied
    timetable (複製自編號 x): the requirement and its rows both change."""
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "EDITING", source_status=source_status)

    data = _reassign_ok(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id
    )

    assert data["updated_schedule_row_count"] == 2
    assert _required_teacher_id(db_session, world.english_requirement.id) == world.new_teacher.id
    english_rows = _rows_of(db_session, world.version.id, world.english_requirement.id)
    assert [r.teacher_id for r in english_rows] == [world.new_teacher.id] * 2


def test_reassign_to_inactive_teacher_returns_409(
    client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    teacher = db_session.get(Teacher, world.new_teacher.id)
    assert teacher is not None
    teacher.is_active = False
    db_session.commit()
    before = _snapshot(db_session)

    response = _reassign(
        client, world.version.id, world.english_requirement.id, world.new_teacher.id
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "無法指派已停用的老師"
    assert _snapshot(db_session) == before


# --- Isolation ---


def _record_rows(db: Session, version_id: int) -> list[tuple[object, ...]]:
    """Every column of one record's requirements and Schedule rows
    (snapshot rows are (model, id, *columns); both tables' first column
    after id is schedule_version_id)."""
    return [
        row
        for row in _snapshot(db)
        if row[0] in ("ClassSubjectRequirement", "Schedule") and row[2] == version_id
    ]


def test_next_semester_copy_change_teacher_and_save(
    client: TestClient, db_session: Session
) -> None:
    """v3, end to end (item 13): 複製此課表 into the next semester, 手動編輯,
    換教師 in the working copy, 儲存課表 -> a new 手動排課 record with the
    new teacher; the copy and its source are left exactly as they were."""
    world = _build_world(db_session)
    mark_status_in_db(db_session, world.version.id, "AUTO")
    next_semester = world.builder.semester_in_year(number=2)
    copied = client.post(
        f"/api/v1/schedule-versions/{world.version.id}/copy",
        json={"target_semester_id": next_semester.id},
    ).json()
    assert copied["status"] == "COPIED"
    working_copy = client.post(f"/api/v1/schedule-versions/{copied['id']}/edit").json()
    working_english = db_session.scalars(
        select(ClassSubjectRequirement).where(
            ClassSubjectRequirement.schedule_version_id == working_copy["id"],
            ClassSubjectRequirement.subject_id == world.english.id,
        )
    ).one()
    source_before = _record_rows(db_session, world.version.id)
    copy_before = _record_rows(db_session, copied["id"])

    _reassign_ok(client, working_copy["id"], working_english.id, world.new_teacher.id)
    saved = client.post(f"/api/v1/schedule-versions/{working_copy['id']}/save").json()

    assert saved["id"] == working_copy["id"]
    assert saved["status"] == "MANUAL"
    assert saved["semester_id"] == next_semester.id
    assert _required_teacher_id(db_session, working_english.id) == world.new_teacher.id
    assert {
        row.teacher_id for row in _rows_of(db_session, saved["id"], working_english.id)
    } == {world.new_teacher.id}
    assert _record_rows(db_session, world.version.id) == source_before
    assert _record_rows(db_session, copied["id"]) == copy_before


# --- Atomicity ---


def test_failure_during_check_rolls_back_everything(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The requirement and the Schedule rows are already updated (and
    # flushed) when the check runs -- a failure there must undo both.
    world = _build_world(db_session)
    before = _snapshot(db_session)

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated failure during the schedule check")

    monkeypatch.setattr(schedule_check, "check_schedule_version", fail)

    with pytest.raises(RuntimeError):
        teacher_reassignment.reassign_teacher(
            db_session,
            world.version.id,
            world.english_requirement.id,
            world.new_teacher.id,
            dry_run=False,
        )

    assert _snapshot(db_session) == before


# --- Permissions ---


def test_reassign_unauthenticated_returns_401(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)

    response = _reassign(
        unauthenticated_client,
        world.version.id,
        world.english_requirement.id,
        world.new_teacher.id,
    )

    assert response.status_code == 401


def test_reassign_as_teacher_returns_403(
    teacher_client: TestClient, db_session: Session
) -> None:
    world = _build_world(db_session)
    before = _snapshot(db_session)

    response = _reassign(
        teacher_client, world.version.id, world.english_requirement.id, world.new_teacher.id
    )

    assert response.status_code == 403
    assert _snapshot(db_session) == before
