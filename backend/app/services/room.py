from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.room import Room
from app.schemas.room import RoomCreate, RoomUpdate
from app.services.delete_guidance import room_delete_steps
from app.services.exceptions import (
    DependentRecordsExistError,
    raise_for_integrity_error,
)
from app.services.school_scope import get_in_school, in_school


def create_room(db: Session, room_data: RoomCreate, *, school_id: int) -> Room:
    room = Room(
        school_id=school_id,
        name=room_data.name,
        is_active=True,
        max_classes=room_data.max_classes,
    )
    db.add(room)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(room)
    return room


def get_room(db: Session, room_id: int, *, school_id: int) -> Room | None:
    return get_in_school(db, Room, room_id, school_id)


def get_rooms(
    db: Session, skip: int = 0, limit: int = 100, *, school_id: int
) -> list[Room]:
    stmt = select(Room).where(in_school(Room, school_id)).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_room(
    db: Session, room_id: int, room_data: RoomUpdate, *, school_id: int
) -> Room | None:
    room = get_in_school(db, Room, room_id, school_id)
    if room is None:
        return None

    for field, value in room_data.model_dump(exclude_unset=True).items():
        setattr(room, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(room)
    return room


def delete_room(db: Session, room_id: int, *, school_id: int) -> bool:
    room = get_in_school(db, Room, room_id, school_id)
    if room is None:
        return False

    try:
        db.delete(room)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DependentRecordsExistError(
            f"Room {room_id} cannot be deleted: other records still "
            "reference it.",
            room_delete_steps(db, room_id),
        ) from exc

    return True
