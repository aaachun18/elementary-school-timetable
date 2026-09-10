from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.lesson import Lesson
from app.schemas.lesson import LessonRead
from app.services import lesson as lesson_service

# Lesson has no create/update/delete endpoints -- rows are only produced by
# POST /api/v1/schedule-versions/{id}/generate-lessons (see
# routers/schedule_version.py). This router is read-only.
router = APIRouter(
    prefix="/api/v1/lessons",
    tags=["lessons"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/", response_model=list[LessonRead])
def list_lessons(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[Lesson]:
    return lesson_service.get_lessons(db, skip=skip, limit=limit)


@router.get("/{lesson_id}", response_model=LessonRead)
def get_lesson(lesson_id: int, db: Session = Depends(get_db)) -> Lesson:
    lesson = lesson_service.get_lesson(db, lesson_id)
    if lesson is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
        )
    return lesson
