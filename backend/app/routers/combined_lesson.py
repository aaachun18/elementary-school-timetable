from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
)
from app.database import get_db
from app.models.user import User
from app.schemas.combined_lesson import (
    CombinedLessonCreate,
    CombinedLessonRead,
    CombinedLessonUpdate,
)
from app.services import combined_lesson as combined_lesson_service

# 共同排課 (併班上課) of a 排課紀錄 -- the wizard's 共同排課 step. Reading is
# open to the school's members (a TEACHER: published records only);
# writing to the 教學組長, while the record is 尚未排課.
router = APIRouter(
    prefix="/api/v1/combined-lessons",
    tags=["combined_lessons"],
    dependencies=[Depends(require_school_member)],
)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


@router.get("/", response_model=list[CombinedLessonRead])
def list_combined_lessons(
    schedule_version_id: int,
    current_user: User = Depends(require_school_member),
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[CombinedLessonRead]:
    result = combined_lesson_service.get_combined_lessons(
        db, schedule_version_id, school_id=school_id, role=current_user.role
    )
    if result is None:
        raise _not_found("ScheduleVersion not found")
    return result


@router.post("/", response_model=CombinedLessonRead, status_code=status.HTTP_201_CREATED)
def create_combined_lesson(
    data: CombinedLessonCreate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> CombinedLessonRead:
    result = combined_lesson_service.create_combined_lesson(db, data, school_id=school_id)
    if result is None:
        raise _not_found("ScheduleVersion not found")
    return result


@router.put("/{combined_lesson_id}", response_model=CombinedLessonRead)
def update_combined_lesson(
    combined_lesson_id: int,
    data: CombinedLessonUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> CombinedLessonRead:
    result = combined_lesson_service.update_combined_lesson(
        db, combined_lesson_id, data, school_id=school_id
    )
    if result is None:
        raise _not_found("CombinedLesson not found")
    return result


@router.delete("/{combined_lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_combined_lesson(
    combined_lesson_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> Response:
    if not combined_lesson_service.delete_combined_lesson(
        db, combined_lesson_id, school_id=school_id
    ):
        raise _not_found("CombinedLesson not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
