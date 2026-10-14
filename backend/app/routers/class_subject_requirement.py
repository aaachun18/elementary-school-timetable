from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.user import User
from app.schemas.class_subject_requirement import (
    ClassSubjectRequirementCreate,
    ClassSubjectRequirementRead,
    ClassSubjectRequirementUpdate,
)
from app.services import class_subject_requirement as requirement_service

# Task 73: every Read field except is_locked comes straight from the row.
_COLUMN_FIELDS = tuple(
    field for field in ClassSubjectRequirementRead.model_fields if field != "is_locked"
)


def _to_read(
    requirement: ClassSubjectRequirement, *, is_locked: bool
) -> ClassSubjectRequirementRead:
    return ClassSubjectRequirementRead(
        **{field: getattr(requirement, field) for field in _COLUMN_FIELDS},
        is_locked=is_locked,
    )


def _to_read_one(
    db: Session, requirement: ClassSubjectRequirement
) -> ClassSubjectRequirementRead:
    return _to_read(
        requirement,
        is_locked=requirement_service.is_used_by_locked_schedule(db, requirement.id),
    )


router = APIRouter(
    prefix="/api/v1/class-subject-requirements",
    tags=["class_subject_requirements"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/",
    response_model=ClassSubjectRequirementRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_class_subject_requirement(
    requirement_data: ClassSubjectRequirementCreate, db: Session = Depends(get_db)
) -> ClassSubjectRequirementRead:
    requirement = requirement_service.create_class_subject_requirement(db, requirement_data)
    return _to_read_one(db, requirement)


@router.get("/", response_model=list[ClassSubjectRequirementRead])
def list_class_subject_requirements(
    skip: int = 0,
    limit: int = 100,
    semester_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ClassSubjectRequirementRead]:
    # Task 72: a TEACHER only sees requirements of semesters with a
    # PUBLISHED version -- a silent filter, same as /schedules (Task 43).
    requirements = requirement_service.get_class_subject_requirements(
        db,
        skip=skip,
        limit=limit,
        semester_id=semester_id,
        role=current_user.role,
    )
    # Task 73: one query for the whole page's is_locked flags.
    locked_ids = requirement_service.locked_requirement_ids(
        db, [requirement.id for requirement in requirements]
    )
    return [
        _to_read(requirement, is_locked=requirement.id in locked_ids)
        for requirement in requirements
    ]


@router.get("/{requirement_id}", response_model=ClassSubjectRequirementRead)
def get_class_subject_requirement(
    requirement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassSubjectRequirementRead:
    # Task 72: a hidden requirement is the same 404 as a missing one.
    requirement = requirement_service.get_class_subject_requirement(
        db, requirement_id, role=current_user.role
    )
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ClassSubjectRequirement not found",
        )
    return _to_read_one(db, requirement)


@router.patch(
    "/{requirement_id}",
    response_model=ClassSubjectRequirementRead,
    dependencies=[Depends(require_admin)],
)
def update_class_subject_requirement(
    requirement_id: int,
    requirement_data: ClassSubjectRequirementUpdate,
    db: Session = Depends(get_db),
) -> ClassSubjectRequirementRead:
    requirement = requirement_service.update_class_subject_requirement(
        db, requirement_id, requirement_data
    )
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ClassSubjectRequirement not found",
        )
    return _to_read_one(db, requirement)


@router.delete(
    "/{requirement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_class_subject_requirement(
    requirement_id: int, db: Session = Depends(get_db)
) -> None:
    deleted = requirement_service.delete_class_subject_requirement(
        db, requirement_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ClassSubjectRequirement not found",
        )
