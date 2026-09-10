from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.schemas.class_subject_requirement import (
    ClassSubjectRequirementCreate,
    ClassSubjectRequirementRead,
    ClassSubjectRequirementUpdate,
)
from app.services import class_subject_requirement as requirement_service

router = APIRouter(
    prefix="/api/v1/class-subject-requirements", tags=["class_subject_requirements"]
)


@router.post(
    "/",
    response_model=ClassSubjectRequirementRead,
    status_code=status.HTTP_201_CREATED,
)
def create_class_subject_requirement(
    requirement_data: ClassSubjectRequirementCreate, db: Session = Depends(get_db)
) -> ClassSubjectRequirement:
    return requirement_service.create_class_subject_requirement(db, requirement_data)


@router.get("/", response_model=list[ClassSubjectRequirementRead])
def list_class_subject_requirements(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[ClassSubjectRequirement]:
    return requirement_service.get_class_subject_requirements(
        db, skip=skip, limit=limit
    )


@router.get("/{requirement_id}", response_model=ClassSubjectRequirementRead)
def get_class_subject_requirement(
    requirement_id: int, db: Session = Depends(get_db)
) -> ClassSubjectRequirement:
    requirement = requirement_service.get_class_subject_requirement(
        db, requirement_id
    )
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ClassSubjectRequirement not found",
        )
    return requirement


@router.patch("/{requirement_id}", response_model=ClassSubjectRequirementRead)
def update_class_subject_requirement(
    requirement_id: int,
    requirement_data: ClassSubjectRequirementUpdate,
    db: Session = Depends(get_db),
) -> ClassSubjectRequirement:
    requirement = requirement_service.update_class_subject_requirement(
        db, requirement_id, requirement_data
    )
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ClassSubjectRequirement not found",
        )
    return requirement


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
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
