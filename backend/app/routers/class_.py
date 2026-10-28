from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
)
from app.database import get_db
from app.models.grade_class import Class
from app.schemas.class_ import ClassBatchCreate, ClassCreate, ClassRead
from app.schemas.deactivation import DeactivationImpactRead
from app.services import class_ as class_service
from app.services.deactivation import DeactivationImpact, deactivation_impact

# No PATCH: a class is only created, deactivated / reactivated and deleted.
router = APIRouter(
    prefix="/api/v1/classes",
    tags=["classes"],
    dependencies=[Depends(require_school_member)],
)


@router.post("/", response_model=ClassRead, status_code=status.HTTP_201_CREATED)
def create_class(
    class_data: ClassCreate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> Class:
    return class_service.create_class(db, class_data, school_id=school_id)


# 學校資料 > 班級 > 批次新增.
@router.post("/batch", response_model=list[ClassRead], status_code=status.HTTP_201_CREATED)
def create_classes_batch(
    batch: ClassBatchCreate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> list[Class]:
    return class_service.create_classes_batch(db, batch, school_id=school_id)


@router.get("/", response_model=list[ClassRead])
def list_classes(
    skip: int = 0,
    limit: int = 100,
    grade_id: int | None = None,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[Class]:
    return class_service.get_classes(
        db, skip=skip, limit=limit, school_id=school_id, grade_id=grade_id
    )


@router.get("/{class_id}", response_model=ClassRead)
def get_class(
    class_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> Class:
    class_obj = class_service.get_class(db, class_id, school_id=school_id)
    if class_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Class not found"
        )
    return class_obj


def _set_active(db: Session, class_id: int, is_active: bool, school_id: int) -> Class:
    class_obj = class_service.set_class_active(db, class_id, is_active, school_id=school_id)
    if class_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Class not found"
        )
    return class_obj


# 停用 / 啟用 (教學組長): the only change a class takes.
@router.post("/{class_id}/deactivate", response_model=ClassRead)
def deactivate_class(
    class_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> Class:
    return _set_active(db, class_id, False, school_id)


@router.post("/{class_id}/activate", response_model=ClassRead)
def activate_class(
    class_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> Class:
    return _set_active(db, class_id, True, school_id)


@router.get("/{class_id}/deactivation-impact", response_model=DeactivationImpactRead)
def class_deactivation_impact(
    class_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> DeactivationImpact:
    if class_service.get_class(db, class_id, school_id=school_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Class not found"
        )
    return deactivation_impact(db, "class", class_id)


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(
    class_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> None:
    deleted = class_service.delete_class(db, class_id, school_id=school_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Class not found"
        )
