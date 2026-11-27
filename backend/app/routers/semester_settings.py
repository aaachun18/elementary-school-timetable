from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
)
from app.database import get_db
from app.models.user import User
from app.schemas.semester_settings import (
    GradeTimeSlotsRead,
    GradeTimeSlotsUpdate,
    SemesterTeacherRead,
    SemesterTeachersUpdate,
)
from app.services import semester_settings as settings_service

# Task 98 / v3: one 排課紀錄's scheduling settings (the wizard's 教師設定 and
# 年級與可排節次). Reading: any account of the school; changing: the
# 教學組長, and only while the record is 尚未排課 (409 otherwise).
router = APIRouter(
    prefix="/api/v1/schedule-versions",
    tags=["semester_settings"],
    dependencies=[Depends(require_school_member)],
)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


@router.get("/{schedule_version_id}/teachers", response_model=list[SemesterTeacherRead])
def list_semester_teachers(
    schedule_version_id: int,
    current_user: User = Depends(require_school_member),
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[SemesterTeacherRead]:
    teachers = settings_service.get_semester_teachers(
        db, schedule_version_id, school_id=school_id, role=current_user.role
    )
    if teachers is None:
        raise _not_found("ScheduleVersion not found")
    return teachers


@router.put("/{schedule_version_id}/teachers", response_model=list[SemesterTeacherRead])
def replace_semester_teachers(
    schedule_version_id: int,
    data: SemesterTeachersUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> list[SemesterTeacherRead]:
    teachers = settings_service.replace_semester_teachers(
        db, schedule_version_id, data, school_id=school_id
    )
    if teachers is None:
        raise _not_found("ScheduleVersion not found")
    return teachers


@router.get("/{schedule_version_id}/grade-time-slots", response_model=list[GradeTimeSlotsRead])
def list_grade_time_slots(
    schedule_version_id: int,
    current_user: User = Depends(require_school_member),
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[GradeTimeSlotsRead]:
    grade_slots = settings_service.get_grade_time_slots(
        db, schedule_version_id, school_id=school_id, role=current_user.role
    )
    if grade_slots is None:
        raise _not_found("ScheduleVersion not found")
    return grade_slots


@router.put(
    "/{schedule_version_id}/grades/{grade_id}/time-slots", response_model=GradeTimeSlotsRead
)
def replace_grade_time_slots(
    schedule_version_id: int,
    grade_id: int,
    data: GradeTimeSlotsUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> GradeTimeSlotsRead:
    grade_slots = settings_service.replace_grade_time_slots(
        db, schedule_version_id, grade_id, data.time_slot_ids, school_id=school_id
    )
    if grade_slots is None:
        raise _not_found("ScheduleVersion or grade not found")
    return grade_slots
