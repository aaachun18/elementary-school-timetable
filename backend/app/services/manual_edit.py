"""v3: 手動編輯課表 and 儲存課表.

A saved timetable never changes in place. Starting a manual edit copies
the record -- settings and timetable -- into a hidden working copy
(status EDITING, no number, editing_source_id = the record); every manual
adjustment (move, swap, place, change room, change teacher) changes only
that copy. Leaving without saving deletes it (DELETE
/schedule-versions/{copy id}). 儲存課表 then:

- the record is 手動排課 and not published -> the copy's contents replace
  the record's (same 編號, same row), and the copy disappears;
- otherwise (自動排課, 複製自編號 x, or a published record) -> the copy
  becomes a new 手動排課 record with the school's next 編號; the record it
  came from is unchanged.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.schedule_version import (
    EDITING,
    MANUAL,
    TIMETABLE_STATUSES,
    ScheduleVersion,
)
from app.services.exceptions import RecordStatusError, raise_for_integrity_error
from app.services.schedule_version import next_version_number
from app.services.version_contents import (
    stage_copy_settings,
    stage_copy_timetable,
    stage_delete_contents,
    stage_move_contents,
)

EDIT_WITHOUT_TIMETABLE_MESSAGE = "這筆排課紀錄還沒有課表，無法手動編輯"
NOT_A_WORKING_COPY_MESSAGE = "這不是編輯中的課表，無法儲存"


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    except Exception:
        # Not swallowed: one transaction -- nothing half-done remains.
        db.rollback()
        raise


def _stage_delete_working_copies(db: Session, source_id: int) -> None:
    """Earlier working copies of the record (an edit left without saving
    or discarding, e.g. a closed tab) -- a new edit always starts from the
    saved timetable."""
    for working_copy in db.scalars(
        select(ScheduleVersion).where(ScheduleVersion.editing_source_id == source_id)
    ).all():
        stage_delete_contents(db, working_copy.id)
        db.delete(working_copy)
    db.flush()


def start_editing(db: Session, schedule_version_id: int) -> ScheduleVersion | None:
    """手動編輯課表: a fresh working copy of the record. None if the record
    doesn't exist (caller -> 404); a record without a timetable (尚未排課,
    or a working copy itself) can't be edited (409)."""
    source = db.get(ScheduleVersion, schedule_version_id)
    if source is None:
        return None
    if source.status not in TIMETABLE_STATUSES:
        raise RecordStatusError(EDIT_WITHOUT_TIMETABLE_MESSAGE)

    working_copy = ScheduleVersion(
        school_id=source.school_id,
        semester_id=source.semester_id,
        version_number=None,
        status=EDITING,
        is_published=False,
        editing_source_id=source.id,
    )
    try:
        _stage_delete_working_copies(db, source.id)
        db.add(working_copy)
        db.flush()
        lesson_id_map = stage_copy_settings(db, source.id, working_copy.id)
        stage_copy_timetable(db, source.id, working_copy.id, lesson_id_map)
    except Exception:
        db.rollback()
        raise
    _commit(db)
    db.refresh(working_copy)
    return working_copy


def _overwrites_source(source: ScheduleVersion) -> bool:
    """Only an unpublished 手動排課 record is saved over; every other
    record keeps its timetable and gets a new 手動排課 record next to it."""
    return source.status == MANUAL and not source.is_published


def save_editing(db: Session, working_copy_id: int) -> ScheduleVersion | None:
    """儲存課表 (see the module docstring). None if the working copy doesn't
    exist (caller -> 404); a record that is not a working copy -> 409.
    Returns the record the edit was saved as."""
    working_copy = db.get(ScheduleVersion, working_copy_id)
    if working_copy is None:
        return None
    if working_copy.status != EDITING or working_copy.editing_source_id is None:
        raise RecordStatusError(NOT_A_WORKING_COPY_MESSAGE)
    source = db.get(ScheduleVersion, working_copy.editing_source_id)
    assert source is not None  # deleting a record deletes its working copies

    try:
        if _overwrites_source(source):
            stage_delete_contents(db, source.id)
            stage_move_contents(db, working_copy.id, source.id)
            db.delete(working_copy)
            source.updated_at = func.now()
            saved = source
        else:
            working_copy.status = MANUAL
            working_copy.version_number = next_version_number(db, source.school_id)
            working_copy.editing_source_id = None
            # The new record dates from the save, not from the edit's start.
            working_copy.created_at = func.now()
            saved = working_copy
    except Exception:
        db.rollback()
        raise
    _commit(db)
    db.refresh(saved)
    return saved
