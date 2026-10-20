import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear, Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class, Grade
from app.models.room import Room
from app.models.school import School
from app.models.semester_grade_time_slot import SemesterGradeTimeSlot
from app.models.semester_teacher import SemesterTeacher, SemesterTeacherUnavailability
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.models.time_slot import TimeSlot
from app.services.school_scope import get_in_school
from tests.conftest import get_test_school_id, time_slot_at

# Task 98 (Task 3 of the wizard redesign): the per-semester scheduling
# settings tables, the grade level range and the requirement's special
# room. Only the schema and its rules -- the engine starts reading them in
# the next Task.



class World:
    """One school's semester, grade, teacher and time slot, written straight
    to the database."""

    def __init__(self, db: Session, school_id: int) -> None:
        self.db = db
        year = AcademicYear(school_id=school_id, year=115, is_active=True)
        self.grade = Grade(school_id=school_id, name="一年級", level=1)
        self.teacher = Teacher(
            school_id=school_id,
            name="甲老師",
            is_active=True,
            min_weekly_periods=0,
            max_weekly_periods=0,
        )
        self.slot = time_slot_at(db, 1, 1, is_teaching_period=True, school_id=school_id)
        self.room = Room(school_id=school_id, name="自然教室", is_active=True)
        self.subject = Subject(school_id=school_id, name="自然", is_active=True)
        db.add_all([year, self.grade, self.teacher, self.slot, self.room, self.subject])
        db.flush()
        self.semester = Semester(academic_year_id=year.id, number=1, is_active=True)
        self.class_ = Class(grade_id=self.grade.id, name="一年甲班")
        db.add_all([self.semester, self.class_])
        db.commit()

    def semester_teacher(self, min_periods: int = 2, max_periods: int = 20) -> SemesterTeacher:
        row = SemesterTeacher(
            semester_id=self.semester.id,
            teacher_id=self.teacher.id,
            min_weekly_periods=min_periods,
            max_weekly_periods=max_periods,
        )
        self.db.add(row)
        self.db.commit()
        return row


@pytest.fixture
def world(db_session: Session) -> World:
    return World(db_session, get_test_school_id(db_session))


# --- grade level 1-12 (國小 1-6, 國中 7-9, 高中 10-12) ---


@pytest.mark.parametrize("level", [1, 6, 7, 9, 10, 12])
def test_database_accepts_grade_levels_1_to_12(db_session: Session, level: int) -> None:
    db_session.add(Grade(school_id=get_test_school_id(db_session), name="年級", level=level))

    db_session.commit()


@pytest.mark.parametrize("level", [0, 13, -1])
def test_database_refuses_grade_level_outside_1_to_12(db_session: Session, level: int) -> None:
    db_session.add(Grade(school_id=get_test_school_id(db_session), name="錯", level=level))

    with pytest.raises(IntegrityError):
        db_session.commit()


# --- SemesterTeacher ---


def test_semester_teacher_once_per_semester(world: World, db_session: Session) -> None:
    world.semester_teacher()

    with pytest.raises(IntegrityError):
        world.semester_teacher()


@pytest.mark.parametrize(("min_periods", "max_periods"), [(5, 4), (-1, 4)])
def test_semester_teacher_periods_range_checked(
    world: World, min_periods: int, max_periods: int
) -> None:
    with pytest.raises(IntegrityError):
        world.semester_teacher(min_periods, max_periods)


def test_semester_teacher_zero_range_allowed(world: World) -> None:
    row = world.semester_teacher(0, 0)

    assert (row.min_weekly_periods, row.max_weekly_periods) == (0, 0)


# --- SemesterTeacherUnavailability ---


def test_unavailability_once_per_slot(world: World, db_session: Session) -> None:
    semester_teacher = world.semester_teacher()
    db_session.add(
        SemesterTeacherUnavailability(
            semester_teacher_id=semester_teacher.id, time_slot_id=world.slot.id
        )
    )
    db_session.commit()

    db_session.add(
        SemesterTeacherUnavailability(
            semester_teacher_id=semester_teacher.id, time_slot_id=world.slot.id
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_unavailabilities_listed_on_semester_teacher(world: World, db_session: Session) -> None:
    semester_teacher = world.semester_teacher()
    db_session.add(
        SemesterTeacherUnavailability(
            semester_teacher_id=semester_teacher.id, time_slot_id=world.slot.id
        )
    )
    db_session.commit()
    db_session.refresh(semester_teacher)

    assert [row.time_slot_id for row in semester_teacher.unavailabilities] == [world.slot.id]


# --- SemesterGradeTimeSlot ---


def test_grade_time_slot_once_per_semester_grade_slot(world: World, db_session: Session) -> None:
    def allowed() -> SemesterGradeTimeSlot:
        return SemesterGradeTimeSlot(
            semester_id=world.semester.id, grade_id=world.grade.id, time_slot_id=world.slot.id
        )

    db_session.add(allowed())
    db_session.commit()
    db_session.add(allowed())

    with pytest.raises(IntegrityError):
        db_session.commit()


# --- ClassSubjectRequirement.required_room_id ---


def test_requirement_stores_required_room(world: World, db_session: Session) -> None:
    requirement = ClassSubjectRequirement(
        semester_id=world.semester.id,
        class_id=world.class_.id,
        subject_id=world.subject.id,
        weekly_periods=1,
        required_room_id=world.room.id,
    )
    db_session.add(requirement)
    db_session.commit()
    db_session.refresh(requirement)

    assert requirement.required_room is not None
    assert requirement.required_room.name == "自然教室"


def test_requirement_required_room_must_exist(world: World, db_session: Session) -> None:
    db_session.add(
        ClassSubjectRequirement(
            semester_id=world.semester.id,
            class_id=world.class_.id,
            subject_id=world.subject.id,
            weekly_periods=1,
            required_room_id=999999,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


# --- school scope ---


def test_new_tables_are_scoped_by_school(world: World, db_session: Session) -> None:
    other_school = School(name="別的學校", is_active=True)
    db_session.add(other_school)
    db_session.commit()
    semester_teacher = world.semester_teacher()
    unavailability = SemesterTeacherUnavailability(
        semester_teacher_id=semester_teacher.id, time_slot_id=world.slot.id
    )
    grade_slot = SemesterGradeTimeSlot(
        semester_id=world.semester.id, grade_id=world.grade.id, time_slot_id=world.slot.id
    )
    db_session.add_all([unavailability, grade_slot])
    db_session.commit()
    own_school_id = get_test_school_id(db_session)

    for model, row_id in (
        (SemesterTeacher, semester_teacher.id),
        (SemesterTeacherUnavailability, unavailability.id),
        (SemesterGradeTimeSlot, grade_slot.id),
    ):
        assert get_in_school(db_session, model, row_id, own_school_id) is not None
        assert get_in_school(db_session, model, row_id, other_school.id) is None
