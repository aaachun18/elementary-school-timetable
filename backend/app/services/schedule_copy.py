"""v3: the two ways a 排課紀錄 is copied into a new record.

- copy_settings (複製此次排課設定): every setting -- teachers, grade slots,
  requirements and their lessons -- into a new 尚未排課 record of the same
  semester, to be changed and scheduled again. No timetable.
- copy_timetable (複製此課表): settings AND timetable into a new 複製自編號 x
  record, of any semester in the same academic year (e.g. the next
  semester, whose teachers can then be changed in a manual edit).

Copies are verbatim: no conflict check, no re-scheduling (GET .../check is
how the caller finds out). The source is only ever read. Each copy is one
transaction: any failure rolls back the whole copy, leaving nothing behind.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_year import Semester
from app.models.schedule_version import (
    COPIED,
    NOT_SCHEDULED,
    TIMETABLE_STATUSES,
    ScheduleVersion,
)
from app.services.exceptions import (
    CopyAcrossAcademicYearsError,
    RecordStatusError,
    TargetSemesterNotFoundError,
    raise_for_integrity_error,
)
from app.services.schedule_version import next_version_number
from app.services.school_scope import get_in_school
from app.services.version_contents import stage_copy_settings, stage_copy_timetable

COPY_WITHOUT_TIMETABLE_MESSAGE = "這筆排課紀錄還沒有課表，無法複製課表"
COPY_WORKING_COPY_MESSAGE = "編輯中的課表不能複製，請先儲存課表"


def _resolve_target_semester_id(
    db: Session, source: ScheduleVersion, target_semester_id: int | None
) -> int:
    """The semester the copy belongs to: the source's own when omitted,
    otherwise one of the same school (else 404) and academic year (else
    409). Only reads."""
    if target_semester_id is None or target_semester_id == source.semester_id:
        return source.semester_id
    target_semester = get_in_school(db, Semester, target_semester_id, source.school_id)
    if target_semester is None:
        raise TargetSemesterNotFoundError(f"Semester {target_semester_id} does not exist.")
    source_semester = db.get(Semester, source.semester_id)
    assert source_semester is not None  # FK on schedule_versions.semester_id
    if target_semester.academic_year_id != source_semester.academic_year_id:
        raise CopyAcrossAcademicYearsError(
            f"Semester {target_semester_id} is not in the same academic year "
            f"as semester {source.semester_id}."
        )
    return target_semester_id


def _create_copy(
    db: Session,
    source: ScheduleVersion,
    new_version: ScheduleVersion,
    *,
    with_timetable: bool,
) -> ScheduleVersion:
    """Stages the new record and its copied contents, then commits -- or
    rolls everything back."""
    try:
        db.add(new_version)
        db.flush()
        lesson_id_map = stage_copy_settings(db, source.id, new_version.id)
        if with_timetable:
            stage_copy_timetable(db, source.id, new_version.id, lesson_id_map)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    except Exception:
        # Not swallowed: any failure part-way through is re-raised after
        # undoing everything staged so far, so no half-copy remains.
        db.rollback()
        raise
    db.refresh(new_version)
    return new_version


def copy_settings(db: Session, source_version_id: int) -> ScheduleVersion | None:
    """複製此次排課設定. None if the source doesn't exist (caller -> 404). A
    working copy can't be copied (409). Returns the new 尚未排課 record."""
    source = db.get(ScheduleVersion, source_version_id)
    if source is None:
        return None
    if source.editing_source_id is not None:
        raise RecordStatusError(COPY_WORKING_COPY_MESSAGE)

    new_version = ScheduleVersion(
        school_id=source.school_id,
        semester_id=source.semester_id,
        version_number=next_version_number(db, source.school_id),
        status=NOT_SCHEDULED,
        is_published=False,
    )
    return _create_copy(db, source, new_version, with_timetable=False)


def copy_timetable(
    db: Session, source_version_id: int, target_semester_id: int | None
) -> ScheduleVersion | None:
    """複製此課表. None if the source doesn't exist (caller -> 404). The
    source must have a timetable (409); the target semester must exist in
    the school (404) and the same academic year (409) -- all checked
    before anything is written. Returns the new 複製自編號 x record."""
    source = db.get(ScheduleVersion, source_version_id)
    if source is None:
        return None
    if source.status not in TIMETABLE_STATUSES:
        raise RecordStatusError(COPY_WITHOUT_TIMETABLE_MESSAGE)
    semester_id = _resolve_target_semester_id(db, source, target_semester_id)

    new_version = ScheduleVersion(
        school_id=source.school_id,
        semester_id=semester_id,
        version_number=next_version_number(db, source.school_id),
        status=COPIED,
        is_published=False,
        copied_from_number=source.version_number,
    )
    return _create_copy(db, source, new_version, with_timetable=True)
