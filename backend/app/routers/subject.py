from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.subject import Subject
from app.schemas.subject import SubjectCreate, SubjectRead, SubjectUpdate
from app.services import subject as subject_service

router = APIRouter(prefix="/api/v1/subjects", tags=["subjects"])


@router.post("/", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(
    subject_data: SubjectCreate, db: Session = Depends(get_db)
) -> Subject:
    return subject_service.create_subject(db, subject_data)


@router.get("/", response_model=list[SubjectRead])
def list_subjects(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[Subject]:
    return subject_service.get_subjects(db, skip=skip, limit=limit)


@router.get("/{subject_id}", response_model=SubjectRead)
def get_subject(subject_id: int, db: Session = Depends(get_db)) -> Subject:
    subject = subject_service.get_subject(db, subject_id)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found"
        )
    return subject


@router.patch("/{subject_id}", response_model=SubjectRead)
def update_subject(
    subject_id: int, subject_data: SubjectUpdate, db: Session = Depends(get_db)
) -> Subject:
    subject = subject_service.update_subject(db, subject_id, subject_data)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found"
        )
    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(subject_id: int, db: Session = Depends(get_db)) -> None:
    deleted = subject_service.delete_subject(db, subject_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found"
        )
