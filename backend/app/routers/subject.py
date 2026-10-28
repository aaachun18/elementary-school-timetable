from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
)
from app.database import get_db
from app.models.subject import Subject
from app.schemas.subject import SubjectCreate, SubjectRead, SubjectUpdate
from app.schemas.deactivation import DeactivationImpactRead
from app.services import subject as subject_service
from app.services.deactivation import DeactivationImpact, deactivation_impact

router = APIRouter(
    prefix="/api/v1/subjects",
    tags=["subjects"],
    dependencies=[Depends(require_school_member)],
)


@router.post("/", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(
    subject_data: SubjectCreate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> Subject:
    return subject_service.create_subject(db, subject_data, school_id=school_id)


@router.get("/", response_model=list[SubjectRead])
def list_subjects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[Subject]:
    return subject_service.get_subjects(db, skip=skip, limit=limit, school_id=school_id)


@router.get("/{subject_id}", response_model=SubjectRead)
def get_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> Subject:
    subject = subject_service.get_subject(db, subject_id, school_id=school_id)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found"
        )
    return subject


@router.get("/{subject_id}/deactivation-impact", response_model=DeactivationImpactRead)
def subject_deactivation_impact(
    subject_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> DeactivationImpact:
    if subject_service.get_subject(db, subject_id, school_id=school_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found"
        )
    return deactivation_impact(db, "subject", subject_id)


@router.patch("/{subject_id}", response_model=SubjectRead)
def update_subject(
    subject_id: int,
    subject_data: SubjectUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> Subject:
    subject = subject_service.update_subject(
        db, subject_id, subject_data, school_id=school_id
    )
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found"
        )
    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> None:
    deleted = subject_service.delete_subject(db, subject_id, school_id=school_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found"
        )
