from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.lesson import Lesson
from app.models.user import User
from app.schemas.lesson import LessonFixTimeSlot, LessonRead
from app.services import lesson as lesson_service

# Lesson has no create/delete endpoints -- rows are only produced by
# POST /api/v1/schedule-versions/{id}/generate-lessons (see
# routers/schedule_version.py). The one exception is fix-time-slot below
# (Task 28): a semantic sub-action on an existing Lesson, not a standard
# CRUD update, same pattern as /teachers/{id}/subjects.
router = APIRouter(
    prefix="/api/v1/lessons",
    tags=["lessons"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/", response_model=list[LessonRead])
def list_lessons(
    skip: int = 0,
    limit: int = 100,
    semester_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Lesson]:
    # Task 72: a TEACHER only sees Lessons of semesters with a PUBLISHED
    # version -- a silent filter, same as /schedules (Task 43).
    return lesson_service.get_lessons(
        db,
        skip=skip,
        limit=limit,
        semester_id=semester_id,
        role=current_user.role,
    )


@router.get("/{lesson_id}", response_model=LessonRead)
def get_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Lesson:
    # Task 72: a hidden Lesson is the same 404 as a missing one.
    lesson = lesson_service.get_lesson(db, lesson_id, role=current_user.role)
    if lesson is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
        )
    return lesson


# --- fix-time-slot: pin/unpin this Lesson's time slot before scheduling
# (Task 28). InvalidReferenceError from an unknown time_slot_id is
# intentionally not caught here -- the global exception handler in main.py
# converts it to 422. ---


@router.patch(
    "/{lesson_id}/fix-time-slot",
    response_model=LessonRead,
    dependencies=[Depends(require_admin)],
)
def fix_lesson_time_slot(
    lesson_id: int, body: LessonFixTimeSlot, db: Session = Depends(get_db)
) -> Lesson:
    lesson = lesson_service.fix_lesson_time_slot(db, lesson_id, body.time_slot_id)
    if lesson is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
        )
    return lesson
