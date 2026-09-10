from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.models.time_slot import TimeSlot
from app.schemas.subject import SubjectRead
from app.schemas.teacher import (
    TeacherAvailabilityCreate,
    TeacherCreate,
    TeacherRead,
    TeacherSubjectCreate,
    TeacherUpdate,
)
from app.schemas.time_slot import TimeSlotRead
from app.services import teacher as teacher_service

router = APIRouter(prefix="/api/v1/teachers", tags=["teachers"])


# --- Standard CRUD ---


@router.post("/", response_model=TeacherRead, status_code=status.HTTP_201_CREATED)
def create_teacher(
    teacher_data: TeacherCreate, db: Session = Depends(get_db)
) -> Teacher:
    return teacher_service.create_teacher(db, teacher_data)


@router.get("/", response_model=list[TeacherRead])
def list_teachers(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[Teacher]:
    return teacher_service.get_teachers(db, skip=skip, limit=limit)


@router.get("/{teacher_id}", response_model=TeacherRead)
def get_teacher(teacher_id: int, db: Session = Depends(get_db)) -> Teacher:
    teacher = teacher_service.get_teacher(db, teacher_id)
    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found"
        )
    return teacher


@router.patch("/{teacher_id}", response_model=TeacherRead)
def update_teacher(
    teacher_id: int, teacher_data: TeacherUpdate, db: Session = Depends(get_db)
) -> Teacher:
    teacher = teacher_service.update_teacher(db, teacher_id, teacher_data)
    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found"
        )
    return teacher


@router.delete("/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)) -> None:
    deleted = teacher_service.delete_teacher(db, teacher_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found"
        )


# --- Semantic sub-resource: teaching qualifications (H5) ---
# Deliberately not a standalone /api/v1/teacher-subjects CRUD -- these
# records only make sense in the context of "this teacher's qualifications".


@router.post(
    "/{teacher_id}/subjects",
    response_model=SubjectRead,
    status_code=status.HTTP_201_CREATED,
)
def add_teacher_subject(
    teacher_id: int, body: TeacherSubjectCreate, db: Session = Depends(get_db)
) -> Subject:
    teacher_subject = teacher_service.add_teacher_subject(
        db, teacher_id, body.subject_id
    )
    return teacher_subject.subject


@router.get("/{teacher_id}/subjects", response_model=list[SubjectRead])
def list_teacher_subjects(
    teacher_id: int, db: Session = Depends(get_db)
) -> list[Subject]:
    subjects = teacher_service.get_teacher_subjects(db, teacher_id)
    if subjects is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found"
        )
    return subjects


@router.delete(
    "/{teacher_id}/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_teacher_subject(
    teacher_id: int, subject_id: int, db: Session = Depends(get_db)
) -> None:
    removed = teacher_service.remove_teacher_subject(db, teacher_id, subject_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Qualification record not found",
        )


# --- Semantic sub-resource: unavailable time slots (H4) ---
# Deliberately not a standalone /api/v1/teacher-availabilities CRUD, for the
# same reason as above.


@router.post(
    "/{teacher_id}/unavailable-slots",
    response_model=TimeSlotRead,
    status_code=status.HTTP_201_CREATED,
)
def add_teacher_unavailable_slot(
    teacher_id: int, body: TeacherAvailabilityCreate, db: Session = Depends(get_db)
) -> TimeSlot:
    teacher_availability = teacher_service.add_teacher_availability(
        db, teacher_id, body.time_slot_id
    )
    return teacher_availability.time_slot


@router.get("/{teacher_id}/unavailable-slots", response_model=list[TimeSlotRead])
def list_teacher_unavailable_slots(
    teacher_id: int, db: Session = Depends(get_db)
) -> list[TimeSlot]:
    slots = teacher_service.get_teacher_unavailable_slots(db, teacher_id)
    if slots is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found"
        )
    return slots


@router.delete(
    "/{teacher_id}/unavailable-slots/{time_slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_teacher_unavailable_slot(
    teacher_id: int, time_slot_id: int, db: Session = Depends(get_db)
) -> None:
    removed = teacher_service.remove_teacher_availability(
        db, teacher_id, time_slot_id
    )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unavailable-slot record not found",
        )
