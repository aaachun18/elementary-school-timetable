from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.school import School
from app.schemas.school import SchoolCreate, SchoolRead, SchoolUpdate
from app.services import school as school_service

router = APIRouter(prefix="/api/v1/schools", tags=["schools"])


@router.post("/", response_model=SchoolRead, status_code=status.HTTP_201_CREATED)
def create_school(
    school_data: SchoolCreate, db: Session = Depends(get_db)
) -> School:
    return school_service.create_school(db, school_data)


@router.get("/", response_model=list[SchoolRead])
def list_schools(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[School]:
    return school_service.get_schools(db, skip=skip, limit=limit)


@router.get("/{school_id}", response_model=SchoolRead)
def get_school(school_id: int, db: Session = Depends(get_db)) -> School:
    school = school_service.get_school(db, school_id)
    if school is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="School not found"
        )
    return school


@router.patch("/{school_id}", response_model=SchoolRead)
def update_school(
    school_id: int, school_data: SchoolUpdate, db: Session = Depends(get_db)
) -> School:
    school = school_service.update_school(db, school_id, school_data)
    if school is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="School not found"
        )
    return school


@router.delete("/{school_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_school(school_id: int, db: Session = Depends(get_db)) -> None:
    # DependentRecordsExistError is intentionally not caught here -- the
    # global exception handler in main.py converts it to 409.
    deleted = school_service.delete_school(db, school_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="School not found"
        )
