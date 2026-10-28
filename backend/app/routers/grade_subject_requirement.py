from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
)
from app.database import get_db
from app.models.grade_subject_requirement import GradeSubjectRequirement
from app.schemas.grade_subject_requirement import (
    GradeSubjectRequirementCreate,
    GradeSubjectRequirementRead,
    GradeSubjectRequirementUpdate,
)
from app.services import grade_subject_requirement as grade_requirement_service

router = APIRouter(
    prefix="/api/v1/grade-subject-requirements",
    tags=["grade_subject_requirements"],
    dependencies=[Depends(require_school_member)],
)


@router.post(
    "/", response_model=GradeSubjectRequirementRead, status_code=status.HTTP_201_CREATED
)
def create_grade_subject_requirement(
    data: GradeSubjectRequirementCreate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> GradeSubjectRequirement:
    return grade_requirement_service.create_grade_subject_requirement(
        db, data, school_id=school_id
    )


@router.get("/", response_model=list[GradeSubjectRequirementRead])
def list_grade_subject_requirements(
    grade_id: int | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[GradeSubjectRequirement]:
    return grade_requirement_service.get_grade_subject_requirements(
        db, school_id=school_id, grade_id=grade_id, include_inactive=include_inactive
    )


@router.patch("/{requirement_id}", response_model=GradeSubjectRequirementRead)
def update_grade_subject_requirement(
    requirement_id: int,
    data: GradeSubjectRequirementUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> GradeSubjectRequirement:
    requirement = grade_requirement_service.update_grade_subject_requirement(
        db, requirement_id, data, school_id=school_id
    )
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GradeSubjectRequirement not found",
        )
    return requirement


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grade_subject_requirement(
    requirement_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> None:
    deleted = grade_requirement_service.delete_grade_subject_requirement(
        db, requirement_id, school_id=school_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GradeSubjectRequirement not found",
        )
