from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
)
from app.database import get_db
from app.models.time_slot import TimeSlot
from app.schemas.time_slot import TimeSlotBulkUpdate, TimeSlotRead, TimeSlotUpdate
from app.services import time_slot as time_slot_service

# No POST / DELETE: a school's grid is built with the school and fixed.
router = APIRouter(
    prefix="/api/v1/time-slots",
    tags=["time_slots"],
    dependencies=[Depends(require_school_member)],
)


@router.get("/", response_model=list[TimeSlotRead])
def list_time_slots(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[TimeSlot]:
    return time_slot_service.get_time_slots(
        db, skip=skip, limit=limit, school_id=school_id
    )


@router.patch("/", response_model=list[TimeSlotRead])
def update_time_slots(
    data: TimeSlotBulkUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> list[TimeSlot]:
    return time_slot_service.update_time_slots(db, data.time_slots, school_id=school_id)


@router.get("/{time_slot_id}", response_model=TimeSlotRead)
def get_time_slot(
    time_slot_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> TimeSlot:
    time_slot = time_slot_service.get_time_slot(db, time_slot_id, school_id=school_id)
    if time_slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="TimeSlot not found"
        )
    return time_slot


@router.patch("/{time_slot_id}", response_model=TimeSlotRead)
def update_time_slot(
    time_slot_id: int,
    time_slot_data: TimeSlotUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> TimeSlot:
    time_slot = time_slot_service.update_time_slot(
        db, time_slot_id, time_slot_data, school_id=school_id
    )
    if time_slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="TimeSlot not found"
        )
    return time_slot
