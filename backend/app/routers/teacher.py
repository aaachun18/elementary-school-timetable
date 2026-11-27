from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
)
from app.database import get_db
from app.models.teacher import Teacher
from app.schemas.teacher import TeacherRead, TeacherUpdate
from app.services import teacher as teacher_service

# Task 98: read and rename only. A teacher is created / 停用 with its
# 一般老師 account (POST /auth/register, PATCH /users/{id}); its semester
# settings are /semesters/{id}/teachers. The former qualification
# (/subjects) and global unavailable-slot sub-resources are gone with the
# concepts themselves.
router = APIRouter(
    prefix="/api/v1/teachers",
    tags=["teachers"],
    dependencies=[Depends(require_school_member)],
)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")


@router.get("/", response_model=list[TeacherRead])
def list_teachers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[Teacher]:
    return teacher_service.get_teachers(db, skip=skip, limit=limit, school_id=school_id)


@router.get("/{teacher_id}", response_model=TeacherRead)
def get_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> Teacher:
    teacher = teacher_service.get_teacher(db, teacher_id, school_id=school_id)
    if teacher is None:
        raise _not_found()
    return teacher


@router.patch("/{teacher_id}", response_model=TeacherRead)
def update_teacher(
    teacher_id: int,
    teacher_data: TeacherUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> Teacher:
    teacher = teacher_service.update_teacher(db, teacher_id, teacher_data, school_id=school_id)
    if teacher is None:
        raise _not_found()
    return teacher
