from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
)
from app.database import get_db
from app.schemas.semester_settings import (
    GradeTimeSlotsRead,
    GradeTimeSlotsUpdate,
    SemesterTeacherRead,
    SemesterTeachersUpdate,
)
from app.services import semester_settings as settings_service

# Task 98: one semester's scheduling settings (the wizard's steps 4-6 and
# 8). Reading: any account of the school; changing: the 教學組長.
router = APIRouter(
    prefix="/api/v1/semesters",
    tags=["semester_settings"],
    dependencies=[Depends(require_school_member)],
)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


@router.get("/{semester_id}/teachers", response_model=list[SemesterTeacherRead])
def list_semester_teachers(
    semester_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[SemesterTeacherRead]:
    teachers = settings_service.get_semester_teachers(db, semester_id, school_id=school_id)
    if teachers is None:
        raise _not_found("Semester not found")
    return teachers


@router.put("/{semester_id}/teachers", response_model=list[SemesterTeacherRead])
def replace_semester_teachers(
    semester_id: int,
    data: SemesterTeachersUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> list[SemesterTeacherRead]:
    teachers = settings_service.replace_semester_teachers(
        db, semester_id, data, school_id=school_id
    )
    if teachers is None:
        raise _not_found("Semester not found")
    return teachers


@router.get("/{semester_id}/grade-time-slots", response_model=list[GradeTimeSlotsRead])
def list_grade_time_slots(
    semester_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[GradeTimeSlotsRead]:
    grade_slots = settings_service.get_grade_time_slots(db, semester_id, school_id=school_id)
    if grade_slots is None:
        raise _not_found("Semester not found")
    return grade_slots


@router.put(
    "/{semester_id}/grades/{grade_id}/time-slots", response_model=GradeTimeSlotsRead
)
def replace_grade_time_slots(
    semester_id: int,
    grade_id: int,
    data: GradeTimeSlotsUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> GradeTimeSlotsRead:
    grade_slots = settings_service.replace_grade_time_slots(
        db, semester_id, grade_id, data.time_slot_ids, school_id=school_id
    )
    if grade_slots is None:
        raise _not_found("Semester or grade not found")
    return grade_slots
