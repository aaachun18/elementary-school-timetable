"""v3: everything one 排課紀錄 (ScheduleVersion) owns, handled as a whole --
deleting it, copying it into another record, or handing it over to
another record. Every function here only stages changes on the session
(add / delete / flush); the caller decides when to commit or roll back, so
each operation stays one transaction.

A record owns:

    ClassSubjectRequirement --< Lesson      (its settings: 科目需求)
    SemesterTeacher --< SemesterTeacherUnavailability   (教師設定)
    SemesterGradeTimeSlot                   (年級與可排節次)
    Schedule                                (its timetable)

Schedule rows point at Lessons, Lessons at requirements -- so deletes go
timetable first, copies go settings first (the new Lesson ids remap the
copied Schedule rows).
"""

from sqlalchemy import Select, delete, select, update
from sqlalchemy.orm import Session

from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.lesson import Lesson
from app.models.schedule import Schedule
from app.models.semester_grade_time_slot import SemesterGradeTimeSlot
from app.models.semester_teacher import SemesterTeacher, SemesterTeacherUnavailability
from app.services.exceptions import CopySourceInconsistentError

# Every business column of ClassSubjectRequirement, copied verbatim
# (required_teacher_id included even if that teacher is now inactive -- the
# check reports H12 for it). Not copied: id (new row), schedule_version_id
# (set to the target), created_at/updated_at (the new row's own).
# tests/test_schedule_copy.py checks that these two lists together cover
# every column, so a column added to the model later can't be silently
# left out of the copy.
COPIED_REQUIREMENT_FIELDS = (
    "class_id",
    "subject_id",
    "weekly_periods",
    "required_teacher_id",
    "required_room_type",
    "consecutive_limit",
    # Task 87: the pattern travels with the requirement; the copied
    # lessons keep their block fields (below), so blocks stay intact.
    "lesson_pattern",
    # Task 98: the special room is part of the requirement too.
    "required_room_id",
)
NOT_COPIED_REQUIREMENT_FIELDS = ("id", "schedule_version_id", "created_at", "updated_at")


def _requirement_ids(version_id: int) -> Select[tuple[int]]:
    return select(ClassSubjectRequirement.id).where(
        ClassSubjectRequirement.schedule_version_id == version_id
    )


def _semester_teacher_ids(version_id: int) -> Select[tuple[int]]:
    return select(SemesterTeacher.id).where(SemesterTeacher.schedule_version_id == version_id)


# --- delete ---


def stage_delete_timetable(db: Session, version_id: int) -> None:
    db.execute(delete(Schedule).where(Schedule.schedule_version_id == version_id))
    db.flush()


def stage_delete_contents(db: Session, version_id: int) -> None:
    """The record's timetable and every setting it owns, children first."""
    stage_delete_timetable(db, version_id)
    db.execute(
        delete(Lesson).where(Lesson.class_subject_requirement_id.in_(_requirement_ids(version_id)))
    )
    db.execute(
        delete(ClassSubjectRequirement).where(
            ClassSubjectRequirement.schedule_version_id == version_id
        )
    )
    db.execute(
        delete(SemesterTeacherUnavailability).where(
            SemesterTeacherUnavailability.semester_teacher_id.in_(
                _semester_teacher_ids(version_id)
            )
        )
    )
    db.execute(delete(SemesterTeacher).where(SemesterTeacher.schedule_version_id == version_id))
    db.execute(
        delete(SemesterGradeTimeSlot).where(SemesterGradeTimeSlot.schedule_version_id == version_id)
    )
    db.flush()


# --- copy ---


def _stage_copy_requirements_and_lessons(
    db: Session, source_id: int, target_id: int
) -> dict[int, int]:
    """Copies of every requirement of the source and every Lesson under
    them (scheduled or not). Returns {old lesson id: new lesson id}."""
    source_requirements = db.scalars(
        select(ClassSubjectRequirement)
        .where(ClassSubjectRequirement.schedule_version_id == source_id)
        .order_by(ClassSubjectRequirement.id)
    ).all()
    new_requirement_by_old_id = {
        requirement.id: ClassSubjectRequirement(
            schedule_version_id=target_id,
            **{field: getattr(requirement, field) for field in COPIED_REQUIREMENT_FIELDS},
        )
        for requirement in source_requirements
    }
    db.add_all(new_requirement_by_old_id.values())
    db.flush()  # the new requirement ids the Lessons need

    source_lessons = (
        db.scalars(
            select(Lesson)
            .where(Lesson.class_subject_requirement_id.in_(list(new_requirement_by_old_id)))
            .order_by(Lesson.id)
        ).all()
        if new_requirement_by_old_id
        else []
    )
    new_lesson_by_old_id = {
        lesson.id: Lesson(
            class_subject_requirement_id=new_requirement_by_old_id[
                lesson.class_subject_requirement_id
            ].id,
            sequence_number=lesson.sequence_number,
            fixed_time_slot_id=lesson.fixed_time_slot_id,
            block_no=lesson.block_no,
            block_seq=lesson.block_seq,
        )
        for lesson in source_lessons
    }
    db.add_all(new_lesson_by_old_id.values())
    db.flush()  # the new lesson ids the Schedule rows need
    return {old_id: new_lesson.id for old_id, new_lesson in new_lesson_by_old_id.items()}


def _stage_copy_teachers_and_grade_slots(db: Session, source_id: int, target_id: int) -> None:
    for semester_teacher in db.scalars(
        select(SemesterTeacher)
        .where(SemesterTeacher.schedule_version_id == source_id)
        .order_by(SemesterTeacher.id)
    ).all():
        copied = SemesterTeacher(
            schedule_version_id=target_id,
            teacher_id=semester_teacher.teacher_id,
            min_weekly_periods=semester_teacher.min_weekly_periods,
            max_weekly_periods=semester_teacher.max_weekly_periods,
            homeroom_class_id=semester_teacher.homeroom_class_id,
        )
        db.add(copied)
        db.flush()
        db.add_all(
            SemesterTeacherUnavailability(
                semester_teacher_id=copied.id, time_slot_id=row.time_slot_id
            )
            for row in sorted(semester_teacher.unavailabilities, key=lambda row: row.time_slot_id)
        )
    db.add_all(
        SemesterGradeTimeSlot(
            schedule_version_id=target_id,
            grade_id=row.grade_id,
            time_slot_id=row.time_slot_id,
        )
        for row in db.scalars(
            select(SemesterGradeTimeSlot)
            .where(SemesterGradeTimeSlot.schedule_version_id == source_id)
            .order_by(SemesterGradeTimeSlot.id)
        ).all()
    )
    db.flush()


def stage_copy_settings(db: Session, source_id: int, target_id: int) -> dict[int, int]:
    """Every setting of the source record, copied into the target (which
    has none yet). Returns {old lesson id: new lesson id} for
    stage_copy_timetable()."""
    lesson_id_map = _stage_copy_requirements_and_lessons(db, source_id, target_id)
    _stage_copy_teachers_and_grade_slots(db, source_id, target_id)
    return lesson_id_map


def stage_copy_timetable(
    db: Session, source_id: int, target_id: int, lesson_id_map: dict[int, int]
) -> None:
    """A copy of every Schedule row of the source, verbatim (no check, no
    re-scheduling, nulls kept), each moved onto the copied Lesson. A row
    pointing outside the source's own lessons aborts the copy."""
    new_rows: list[Schedule] = []
    for schedule in db.scalars(
        select(Schedule).where(Schedule.schedule_version_id == source_id).order_by(Schedule.id)
    ).all():
        if schedule.lesson_id not in lesson_id_map:
            raise CopySourceInconsistentError(
                f"Schedule {schedule.id} points at Lesson {schedule.lesson_id}, "
                f"which is not under ScheduleVersion {source_id}'s requirements."
            )
        new_rows.append(
            Schedule(
                schedule_version_id=target_id,
                lesson_id=lesson_id_map[schedule.lesson_id],
                teacher_id=schedule.teacher_id,
                time_slot_id=schedule.time_slot_id,
                room_id=schedule.room_id,
            )
        )
    db.add_all(new_rows)
    db.flush()


# --- hand over ---


def stage_move_contents(db: Session, from_id: int, to_id: int) -> None:
    """Every setting and Schedule row of `from_id` now belongs to `to_id`
    (which owns nothing at this point). Lessons and unavailable slots hang
    off rows that move, so they follow."""
    for model in (ClassSubjectRequirement, SemesterTeacher, SemesterGradeTimeSlot, Schedule):
        db.execute(
            update(model)
            .where(model.schedule_version_id == from_id)
            .values(schedule_version_id=to_id)
        )
    db.flush()
