from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.time_slot import TimeSlot
from app.schemas.time_slot import TimeSlotCreate, TimeSlotRead, TimeSlotUpdate
from app.services import time_slot as time_slot_service

router = APIRouter(prefix="/api/v1/time-slots", tags=["time_slots"])


@router.post("/", response_model=TimeSlotRead, status_code=status.HTTP_201_CREATED)
def create_time_slot(
    time_slot_data: TimeSlotCreate, db: Session = Depends(get_db)
) -> TimeSlot:
    return time_slot_service.create_time_slot(db, time_slot_data)


@router.get("/", response_model=list[TimeSlotRead])
def list_time_slots(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[TimeSlot]:
    return time_slot_service.get_time_slots(db, skip=skip, limit=limit)


@router.get("/{time_slot_id}", response_model=TimeSlotRead)
def get_time_slot(time_slot_id: int, db: Session = Depends(get_db)) -> TimeSlot:
    time_slot = time_slot_service.get_time_slot(db, time_slot_id)
    if time_slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="TimeSlot not found"
        )
    return time_slot


@router.patch("/{time_slot_id}", response_model=TimeSlotRead)
def update_time_slot(
    time_slot_id: int, time_slot_data: TimeSlotUpdate, db: Session = Depends(get_db)
) -> TimeSlot:
    time_slot = time_slot_service.update_time_slot(db, time_slot_id, time_slot_data)
    if time_slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="TimeSlot not found"
        )
    return time_slot


@router.delete("/{time_slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_time_slot(time_slot_id: int, db: Session = Depends(get_db)) -> None:
    deleted = time_slot_service.delete_time_slot(db, time_slot_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="TimeSlot not found"
        )
