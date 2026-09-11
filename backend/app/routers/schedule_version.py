from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.schedule_version import ScheduleVersion
from app.schemas.schedule_version import (
    GeneratedLessonInfo,
    GenerateLessonsResult,
    ScheduleVersionCreate,
    ScheduleVersionRead,
    ScheduleVersionUpdate,
)
from app.schemas.scheduler import (
    ConstraintViolationDetail,
    LessonFailureDetail,
    SchedulerFailureDetail,
    SchedulerRunResult,
)
from app.services import schedule_version as schedule_version_service
from app.services import scheduler as scheduler_service

router = APIRouter(
    prefix="/api/v1/schedule-versions",
    tags=["schedule_versions"],
    dependencies=[Depends(get_current_user)],
)


# --- Standard CRUD ---


@router.post(
    "/",
    response_model=ScheduleVersionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_schedule_version(
    version_data: ScheduleVersionCreate, db: Session = Depends(get_db)
) -> ScheduleVersion:
    return schedule_version_service.create_schedule_version(db, version_data)


@router.get("/", response_model=list[ScheduleVersionRead])
def list_schedule_versions(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[ScheduleVersion]:
    return schedule_version_service.get_schedule_versions(db, skip=skip, limit=limit)


@router.get("/{schedule_version_id}", response_model=ScheduleVersionRead)
def get_schedule_version(
    schedule_version_id: int, db: Session = Depends(get_db)
) -> ScheduleVersion:
    schedule_version = schedule_version_service.get_schedule_version(
        db, schedule_version_id
    )
    if schedule_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return schedule_version


@router.patch(
    "/{schedule_version_id}",
    response_model=ScheduleVersionRead,
    dependencies=[Depends(require_admin)],
)
def update_schedule_version(
    schedule_version_id: int,
    version_data: ScheduleVersionUpdate,
    db: Session = Depends(get_db),
) -> ScheduleVersion:
    schedule_version = schedule_version_service.update_schedule_version(
        db, schedule_version_id, version_data
    )
    if schedule_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return schedule_version


@router.delete(
    "/{schedule_version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_schedule_version(
    schedule_version_id: int, db: Session = Depends(get_db)
) -> None:
    deleted = schedule_version_service.delete_schedule_version(
        db, schedule_version_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )


# --- generate-lessons: diff-sync (not standard CRUD) ---
# LessonOverProvisionedError is intentionally not caught here -- the global
# exception handler in main.py converts it to 409.


@router.post(
    "/{schedule_version_id}/generate-lessons",
    response_model=GenerateLessonsResult,
    dependencies=[Depends(require_admin)],
)
def generate_lessons(
    schedule_version_id: int, db: Session = Depends(get_db)
) -> GenerateLessonsResult:
    created = schedule_version_service.generate_lessons(db, schedule_version_id)
    if created is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return GenerateLessonsResult(
        created_lessons=[
            GeneratedLessonInfo(
                lesson_id=lesson.id,
                class_subject_requirement_id=lesson.class_subject_requirement_id,
                sequence_number=lesson.sequence_number,
            )
            for lesson in created
        ],
        created_count=len(created),
    )


# --- run-scheduler ---
# ScheduleVersionAlreadyScheduledError is intentionally not caught here --
# the global exception handler in main.py converts it to 409.


@router.post(
    "/{schedule_version_id}/run-scheduler",
    response_model=SchedulerRunResult,
    dependencies=[Depends(require_admin)],
)
def run_scheduler(
    schedule_version_id: int, db: Session = Depends(get_db)
) -> SchedulerRunResult | JSONResponse:
    outcome = scheduler_service.run_scheduler(db, schedule_version_id)
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )

    if outcome.static_violations is not None:
        # Task 23: an aggregate, summed-up problem was found before the
        # search ever ran -- backtrack_count is always 0 here.
        detail = SchedulerFailureDetail(
            failure_type="STATIC_CHECK_FAILED",
            lesson_failures=[],
            post_hoc_violations=[
                ConstraintViolationDetail.model_validate(violation)
                for violation in outcome.static_violations
            ],
            backtrack_count=0,
        )
        return JSONResponse(status_code=422, content=detail.model_dump())

    result = outcome.search_result
    assert result is not None  # exactly one of the two fields is populated

    if result.success:
        return SchedulerRunResult(
            scheduled_count=len(result.state.assignments) if result.state else 0,
            backtrack_count=result.backtrack_count,
        )

    # failure_type is None only in the one non-search-level failure case:
    # every Lesson placed, but the finished schedule still fails the
    # post-hoc H7 (weekly periods) check -- see SchedulerFailureDetail's
    # docstring for why this gets its own label instead of a null one.
    failure_type = result.failure_type or "REQUIREMENT_PERIODS_MISMATCH"
    detail = SchedulerFailureDetail(
        failure_type=failure_type,
        lesson_failures=[
            LessonFailureDetail(
                lesson_id=failure.lesson_id,
                class_subject_requirement_id=failure.class_subject_requirement_id,
                reasons=[
                    ConstraintViolationDetail.model_validate(reason)
                    for reason in failure.reasons
                ],
            )
            for failure in result.lesson_failures
        ],
        post_hoc_violations=[
            ConstraintViolationDetail.model_validate(violation)
            for violation in result.post_hoc_violations
        ],
        backtrack_count=result.backtrack_count,
    )
    return JSONResponse(
        status_code=422,
        content=detail.model_dump(),
    )
