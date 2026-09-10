from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.grade_class import Class
from app.schemas.class_ import ClassCreate, ClassRead, ClassUpdate
from app.services import class_ as class_service

router = APIRouter(prefix="/api/v1/classes", tags=["classes"])


@router.post("/", response_model=ClassRead, status_code=status.HTTP_201_CREATED)
def create_class(class_data: ClassCreate, db: Session = Depends(get_db)) -> Class:
    return class_service.create_class(db, class_data)


@router.get("/", response_model=list[ClassRead])
def list_classes(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[Class]:
    return class_service.get_classes(db, skip=skip, limit=limit)


@router.get("/{class_id}", response_model=ClassRead)
def get_class(class_id: int, db: Session = Depends(get_db)) -> Class:
    class_obj = class_service.get_class(db, class_id)
    if class_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Class not found"
        )
    return class_obj


@router.patch("/{class_id}", response_model=ClassRead)
def update_class(
    class_id: int, class_data: ClassUpdate, db: Session = Depends(get_db)
) -> Class:
    class_obj = class_service.update_class(db, class_id, class_data)
    if class_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Class not found"
        )
    return class_obj


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(class_id: int, db: Session = Depends(get_db)) -> None:
    deleted = class_service.delete_class(db, class_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Class not found"
        )
