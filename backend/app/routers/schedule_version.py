from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.schedule_version import ScheduleVersion
from app.models.user import User
from app.schemas.schedule_version import (
    GeneratedLessonInfo,
    GenerateLessonsResult,
    ScheduleVersionCopy,
    ScheduleVersionCreate,
    ScheduleVersionRead,
    ScheduleVersionUpdate,
)
from app.schemas.scheduler import (
    ConstraintViolationDetail,
    LessonFailureDetail,
    MoveCandidateSlot,
    MoveCandidatesResult,
    MoveCandidateSwap,
    MoveLessonRequest,
    ScheduleAdjustmentResult,
    ScheduleChangeDetail,
    ScheduleCheckResult,
    SchedulerFailureDetail,
    SwapLessonsRequest,
    SchedulerRunResult,
    TeacherReassignmentRequest,
    TeacherReassignmentResult,
)
from app.services import schedule_adjustment as schedule_adjustment_service
from app.services import schedule_check as schedule_check_service
from app.services import move_candidates as move_candidates_service
from app.services import schedule_copy as schedule_copy_service
from app.services import schedule_version as schedule_version_service
from app.services import scheduler as scheduler_service
from app.services import teacher_reassignment as teacher_reassignment_service

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
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ScheduleVersion]:
    # Task 43: TEACHER only ever sees PUBLISHED versions -- see
    # get_schedule_versions()'s own docstring-equivalent comment in
    # services/schedule_version.py for why this is a silent filter, not a
    # 403.
    return schedule_version_service.get_schedule_versions(
        db, skip=skip, limit=limit, role=current_user.role
    )


@router.get("/{schedule_version_id}", response_model=ScheduleVersionRead)
def get_schedule_version(
    schedule_version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScheduleVersion:
    schedule_version = schedule_version_service.get_schedule_version(
        db, schedule_version_id, role=current_user.role
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


# --- copy (Task 62): new DRAFT from an existing version ---
# TargetSemesterNotFoundError / CopyAcrossAcademicYearsError /
# TargetSemesterHasRequirementsError / CopySourceInconsistentError are
# intentionally not caught here -- the global exception handlers in main.py
# convert them to 404/409.


@router.post(
    "/{schedule_version_id}/copy",
    response_model=ScheduleVersionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def copy_schedule_version(
    schedule_version_id: int,
    copy_data: ScheduleVersionCopy | None = None,
    db: Session = Depends(get_db),
) -> ScheduleVersion:
    target_semester_id = copy_data.target_semester_id if copy_data else None
    new_version = schedule_copy_service.copy_schedule_version(
        db, schedule_version_id, target_semester_id
    )
    if new_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return new_version


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
    result = schedule_version_service.generate_lessons(db, schedule_version_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    created, total_lesson_count = result
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
        total_lesson_count=total_lesson_count,
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
        # Task 23/38: a problem was found before the search ever ran --
        # backtrack_count is always 0 here. static_lesson_failures (Task 38)
        # can be non-empty alongside static_violations in the same response:
        # a whole-batch problem (e.g. teacher workload) and a specific
        # Lesson with zero candidate teachers are independent findings from
        # check_static_feasibility()'s 4 checks, never mutually exclusive.
        assert outcome.static_lesson_failures is not None
        detail = SchedulerFailureDetail(
            failure_type="STATIC_CHECK_FAILED",
            lesson_failures=[
                LessonFailureDetail.model_validate(failure)
                for failure in outcome.static_lesson_failures
            ],
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
            LessonFailureDetail.model_validate(failure)
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


@router.get(
    "/{schedule_version_id}/check",
    response_model=ScheduleCheckResult,
    dependencies=[Depends(require_admin)],
)
def check_schedule_version(
    schedule_version_id: int,
    db: Session = Depends(get_db),
) -> ScheduleCheckResult:
    # Task 61: read-only. Task 72: ADMIN only -- the conflict details (and,
    # for a DRAFT, its content) are an administrative tool, not something
    # the read-only TEACHER role needs; a TEACHER gets 403 for every
    # version, including PUBLISHED ones.
    violations = schedule_check_service.check_schedule_version(
        db, schedule_version_id
    )
    if violations is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return _build_check_result(schedule_version_id, violations)


def _build_check_result(
    schedule_version_id: int, violations: list
) -> ScheduleCheckResult:
    """Shared by /check and /reassign-teacher (Task 63). Task 88: a WARNING
    (TEACHER_MIN_WORKLOAD) is listed and counted, but doesn't make the
    timetable invalid -- is_valid means "no ERROR"."""
    return ScheduleCheckResult(
        schedule_version_id=schedule_version_id,
        is_valid=not schedule_check_service.has_errors(violations),
        violation_count=len(violations),
        violations=[
            ConstraintViolationDetail.model_validate(violation)
            for violation in violations
        ],
    )


# --- reassign-teacher (Task 63): manual adjustment, one requirement ---
# PublishedVersionImmutableError / ReassignmentTargetNotFoundError /
# RequirementSemesterMismatchError / InactiveTeacherAssignmentError are
# intentionally not caught here -- the global exception handlers in main.py
# convert them to 409/404.


@router.post(
    "/{schedule_version_id}/reassign-teacher",
    response_model=TeacherReassignmentResult,
    dependencies=[Depends(require_admin)],
)
def reassign_teacher(
    schedule_version_id: int,
    reassignment: TeacherReassignmentRequest,
    db: Session = Depends(get_db),
) -> TeacherReassignmentResult:
    outcome = teacher_reassignment_service.reassign_teacher(
        db,
        schedule_version_id,
        reassignment.class_subject_requirement_id,
        reassignment.new_teacher_id,
        dry_run=reassignment.dry_run,
    )
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return TeacherReassignmentResult(
        schedule_version_id=schedule_version_id,
        class_subject_requirement_id=reassignment.class_subject_requirement_id,
        previous_teacher_id=outcome.previous_teacher_id,
        new_teacher_id=reassignment.new_teacher_id,
        updated_schedule_row_count=outcome.updated_schedule_row_count,
        dry_run=reassignment.dry_run,
        check=_build_check_result(schedule_version_id, outcome.violations),
    )


# --- move-lesson / swap-lessons (Task 65): manual time-slot adjustments ---
# PublishedVersionImmutableError / ArchivedVersionImmutableError /
# AdjustmentTargetNotFoundError / ScheduleNotInVersionError /
# CannotSwapWithSelfError are intentionally not caught here -- the global
# exception handlers in main.py convert them to 409/404.


def _build_adjustment_result(
    schedule_version_id: int,
    dry_run: bool,
    outcome: schedule_adjustment_service.AdjustmentOutcome | None,
) -> ScheduleAdjustmentResult:
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return ScheduleAdjustmentResult(
        schedule_version_id=schedule_version_id,
        dry_run=dry_run,
        changes=[ScheduleChangeDetail.model_validate(change) for change in outcome.changes],
        check=_build_check_result(schedule_version_id, outcome.violations),
    )


@router.post(
    "/{schedule_version_id}/move-lesson",
    response_model=ScheduleAdjustmentResult,
    dependencies=[Depends(require_admin)],
)
def move_lesson(
    schedule_version_id: int,
    move: MoveLessonRequest,
    db: Session = Depends(get_db),
) -> ScheduleAdjustmentResult:
    outcome = schedule_adjustment_service.move_lesson(
        db,
        schedule_version_id,
        move.schedule_id,
        move.target_time_slot_id,
        move.target_room_id,
        dry_run=move.dry_run,
    )
    return _build_adjustment_result(schedule_version_id, move.dry_run, outcome)


@router.post(
    "/{schedule_version_id}/swap-lessons",
    response_model=ScheduleAdjustmentResult,
    dependencies=[Depends(require_admin)],
)
def swap_lessons(
    schedule_version_id: int,
    swap: SwapLessonsRequest,
    db: Session = Depends(get_db),
) -> ScheduleAdjustmentResult:
    outcome = schedule_adjustment_service.swap_lessons(
        db,
        schedule_version_id,
        swap.schedule_id,
        swap.swap_with_schedule_id,
        dry_run=swap.dry_run,
    )
    return _build_adjustment_result(schedule_version_id, swap.dry_run, outcome)


# --- move-candidates (Task 83): read-only "what if" for every time slot ---
# PublishedVersionImmutableError / ArchivedVersionImmutableError (409) and
# AdjustmentTargetNotFoundError (404) are converted by main.py's handlers.


@router.get(
    "/{schedule_version_id}/move-candidates/{schedule_id}",
    response_model=MoveCandidatesResult,
    dependencies=[Depends(require_admin)],
)
def list_move_candidates(
    schedule_version_id: int,
    schedule_id: int,
    db: Session = Depends(get_db),
) -> MoveCandidatesResult:
    # ADMIN only, like /check (a TEACHER gets 403 before anything is looked
    # up, so it learns nothing about which ids exist). Writes nothing.
    outcome = move_candidates_service.list_move_candidates(
        db, schedule_version_id, schedule_id
    )
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return MoveCandidatesResult(
        schedule_version_id=schedule_version_id,
        schedule_id=outcome.schedule_id,
        current_time_slot_id=outcome.current_time_slot_id,
        baseline=_build_check_result(schedule_version_id, outcome.baseline),
        candidates=[
            MoveCandidateSlot(
                time_slot_id=candidate.time_slot_id,
                available=candidate.available,
                unavailable_reason=candidate.unavailable_reason,
                move=(
                    None
                    if candidate.move is None
                    else _build_check_result(schedule_version_id, candidate.move)
                ),
                swaps=[
                    MoveCandidateSwap(
                        swap_with_schedule_id=swap.swap_with_schedule_id,
                        check=_build_check_result(schedule_version_id, swap.violations),
                    )
                    for swap in candidate.swaps
                ],
            )
            for candidate in outcome.candidates
        ],
    )
