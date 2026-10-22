from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
    require_version_in_school,
)
from app.database import get_db
from app.models.schedule_version import ScheduleVersion
from app.models.user import User
from app.schemas.schedule_version import (
    GeneratedLessonInfo,
    GenerateLessonsResult,
    ScheduleVersionCopyTimetable,
    ScheduleVersionCreate,
    ScheduleVersionRead,
    ScheduleVersionUpdate,
)
from app.schemas.scheduler import (
    BlockMemberDetail,
    ChangeRoomRequest,
    ChangeRoomResult,
    ConstraintViolationDetail,
    LessonFailureDetail,
    MoveCandidateSlot,
    MoveCandidatesResult,
    MoveCandidateSwap,
    MoveLessonRequest,
    PlaceCandidateSlot,
    PlaceCandidatesResult,
    PlacedLessonDetail,
    PlaceLessonRequest,
    PlaceLessonResult,
    PlacementChangeDetail,
    RoomChangeDetail,
    ScheduleAdjustmentResult,
    ScheduleChangeDetail,
    ScheduleCheckResult,
    SchedulerFailureDetail,
    SwapLessonsRequest,
    SchedulerRunResult,
    TeacherReassignmentRequest,
    TeacherReassignmentResult,
    UnscheduledLessonDetail,
    UnscheduledLessonsResult,
    UnsupportedSwapDetail,
)
from app.services import schedule_adjustment as schedule_adjustment_service
from app.services import lesson_placement as lesson_placement_service
from app.services import manual_edit as manual_edit_service
from app.services import room_change as room_change_service
from app.services import schedule_check as schedule_check_service
from app.services import move_candidates as move_candidates_service
from app.services import schedule_copy as schedule_copy_service
from app.services import schedule_version as schedule_version_service
from app.services import scheduler as scheduler_service
from app.services import teacher_reassignment as teacher_reassignment_service

router = APIRouter(
    prefix="/api/v1/schedule-versions",
    tags=["schedule_versions"],
    dependencies=[Depends(require_school_member)],
)


# --- Standard CRUD ---
# Task 98: every endpoint below the CRUD ones acts on one version and is
# gated by require_version_in_school (教學組長 only, version of their own
# school only).


@router.post("/", response_model=ScheduleVersionRead, status_code=status.HTTP_201_CREATED)
def create_schedule_version(
    version_data: ScheduleVersionCreate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> ScheduleVersion:
    return schedule_version_service.create_schedule_version(
        db, version_data, school_id=school_id
    )


@router.get("/", response_model=list[ScheduleVersionRead])
def list_schedule_versions(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_school_member),
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[ScheduleVersion]:
    # Task 43: TEACHER only ever sees published records -- a silent
    # filter, not a 403 (see services/schedule_version.py). Newest first;
    # manual edits' working copies are never listed.
    return schedule_version_service.get_schedule_versions(
        db, skip=skip, limit=limit, school_id=school_id, role=current_user.role
    )


@router.get("/{schedule_version_id}", response_model=ScheduleVersionRead)
def get_schedule_version(
    schedule_version_id: int,
    current_user: User = Depends(require_school_member),
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> ScheduleVersion:
    schedule_version = schedule_version_service.get_schedule_version(
        db, schedule_version_id, school_id=school_id, role=current_user.role
    )
    if schedule_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return schedule_version


@router.patch("/{schedule_version_id}", response_model=ScheduleVersionRead)
def update_schedule_version(
    schedule_version_id: int,
    version_data: ScheduleVersionUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> ScheduleVersion:
    schedule_version = schedule_version_service.update_schedule_version(
        db, schedule_version_id, version_data, school_id=school_id
    )
    if schedule_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return schedule_version


@router.delete("/{schedule_version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule_version(
    schedule_version_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> None:
    deleted = schedule_version_service.delete_schedule_version(
        db, schedule_version_id, school_id=school_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )


def _found(schedule_version: ScheduleVersion | None) -> ScheduleVersion:
    if schedule_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return schedule_version


# --- v3: publishing, copying and manual editing a 排課紀錄 ---
# RecordStatusError / TargetSemesterNotFoundError /
# CopyAcrossAcademicYearsError / CopySourceInconsistentError are
# intentionally not caught here -- the global exception handlers in main.py
# convert them to 404/409.


@router.post(
    "/{schedule_version_id}/publish",
    response_model=ScheduleVersionRead,
    dependencies=[Depends(require_version_in_school)],
)
def publish_schedule_version(
    schedule_version_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> ScheduleVersion:
    """發布此課表: the semester's one published record from now on."""
    return _found(
        schedule_version_service.publish_schedule_version(
            db, schedule_version_id, school_id=school_id
        )
    )


@router.post(
    "/{schedule_version_id}/copy-settings",
    response_model=ScheduleVersionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_version_in_school)],
)
def copy_settings(schedule_version_id: int, db: Session = Depends(get_db)) -> ScheduleVersion:
    """複製此次排課設定: a new 尚未排課 record with the same settings."""
    return _found(schedule_copy_service.copy_settings(db, schedule_version_id))


@router.post(
    "/{schedule_version_id}/copy",
    response_model=ScheduleVersionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_version_in_school)],
)
def copy_timetable(
    schedule_version_id: int,
    copy_data: ScheduleVersionCopyTimetable | None = None,
    db: Session = Depends(get_db),
) -> ScheduleVersion:
    """複製此課表: a new 複製自編號 x record (settings and timetable), of any
    semester of the same academic year."""
    target_semester_id = copy_data.target_semester_id if copy_data else None
    return _found(
        schedule_copy_service.copy_timetable(db, schedule_version_id, target_semester_id)
    )


@router.post(
    "/{schedule_version_id}/edit",
    response_model=ScheduleVersionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_version_in_school)],
)
def start_editing(schedule_version_id: int, db: Session = Depends(get_db)) -> ScheduleVersion:
    """手動編輯課表: a fresh working copy every adjustment then changes.
    Leaving without saving: DELETE the working copy."""
    return _found(manual_edit_service.start_editing(db, schedule_version_id))


@router.post(
    "/{schedule_version_id}/save",
    response_model=ScheduleVersionRead,
    dependencies=[Depends(require_version_in_school)],
)
def save_editing(schedule_version_id: int, db: Session = Depends(get_db)) -> ScheduleVersion:
    """儲存課表 (on the working copy's id): returns the record the edit was
    saved as -- the 手動排課 record itself, or a new 手動排課 record."""
    return _found(manual_edit_service.save_editing(db, schedule_version_id))


# --- generate-lessons: diff-sync (not standard CRUD) ---
# LessonOverProvisionedError is intentionally not caught here -- the global
# exception handler in main.py converts it to 409.


@router.post(
    "/{schedule_version_id}/generate-lessons",
    response_model=GenerateLessonsResult,
    dependencies=[Depends(require_version_in_school)],
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
    dependencies=[Depends(require_version_in_school)],
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
        preferred = outcome.preferred_periods
        return SchedulerRunResult(
            scheduled_count=len(result.state.assignments) if result.state else 0,
            backtrack_count=result.backtrack_count,
            preferred_period_score=preferred.score_after if preferred else 0,
            preferred_period_lesson_count=preferred.preferred_lesson_count if preferred else 0,
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
    dependencies=[Depends(require_version_in_school)],
)
def check_schedule_version(
    schedule_version_id: int,
    db: Session = Depends(get_db),
) -> ScheduleCheckResult:
    # Task 61: read-only. Task 72: 教學組長 only -- the conflict details
    # are an administrative tool, not something the read-only TEACHER role
    # needs; a TEACHER gets 403 for every record, published ones included.
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
# v3: only in the working copy of a copied timetable.
# TimetableLockedError / RecordStatusError / ReassignmentTargetNotFoundError
# / RequirementNotInVersionError / InactiveTeacherAssignmentError are
# intentionally not caught here -- the global exception handlers in main.py
# convert them to 409/404.


@router.post(
    "/{schedule_version_id}/reassign-teacher",
    response_model=TeacherReassignmentResult,
    dependencies=[Depends(require_version_in_school)],
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
# v3: only in a manual edit's working copy. TimetableLockedError /
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
    dependencies=[Depends(require_version_in_school)],
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
    dependencies=[Depends(require_version_in_school)],
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
# TimetableLockedError (409) and AdjustmentTargetNotFoundError (404) are
# converted by main.py's handlers.


def _block_members(
    members: list[move_candidates_service.BlockMember] | None,
) -> list[BlockMemberDetail] | None:
    if members is None:
        return None
    return [BlockMemberDetail.model_validate(member) for member in members]


@router.get(
    "/{schedule_version_id}/move-candidates/{schedule_id}",
    response_model=MoveCandidatesResult,
    dependencies=[Depends(require_version_in_school)],
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
                        block_members=_block_members(swap.block_members),
                    )
                    for swap in candidate.swaps
                ],
                block_members=_block_members(candidate.block_members),
                unsupported_swaps=(
                    None
                    if candidate.unsupported_swaps is None
                    else [
                        UnsupportedSwapDetail.model_validate(item)
                        for item in candidate.unsupported_swaps
                    ]
                ),
            )
            for candidate in outcome.candidates
        ],
    )


# --- Task 92: unscheduled lessons and placing them (decision 28) ---
# TimetableLockedError / LessonNotInVersionError / LessonAlreadyScheduledError /
# InactiveTeacherAssignmentError / PlacementRefusedError (409) and
# AdjustmentTargetNotFoundError (404) are converted by main.py's handlers.


@router.get(
    "/{schedule_version_id}/unscheduled-lessons",
    response_model=UnscheduledLessonsResult,
    dependencies=[Depends(require_version_in_school)],
)
def list_unscheduled_lessons(
    schedule_version_id: int,
    db: Session = Depends(get_db),
) -> UnscheduledLessonsResult:
    # Read-only: any version status.
    lessons = lesson_placement_service.list_unscheduled_lessons(db, schedule_version_id)
    if lessons is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return UnscheduledLessonsResult(
        schedule_version_id=schedule_version_id,
        lessons=[UnscheduledLessonDetail.model_validate(lesson) for lesson in lessons],
    )


@router.get(
    "/{schedule_version_id}/place-candidates/{lesson_id}",
    response_model=PlaceCandidatesResult,
    dependencies=[Depends(require_version_in_school)],
)
def list_place_candidates(
    schedule_version_id: int,
    lesson_id: int,
    teacher_id: int | None = None,
    room_id: int | None = None,
    db: Session = Depends(get_db),
) -> PlaceCandidatesResult:
    # Read-only, working copies only (like move-candidates). Writes nothing.
    outcome = lesson_placement_service.list_place_candidates(
        db, schedule_version_id, lesson_id, teacher_id, room_id
    )
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return PlaceCandidatesResult(
        schedule_version_id=schedule_version_id,
        lesson_id=outcome.lesson_id,
        teacher_id=outcome.teacher_id,
        room_id=outcome.room_id,
        baseline=_build_check_result(schedule_version_id, outcome.baseline),
        candidates=[
            PlaceCandidateSlot(
                time_slot_id=candidate.time_slot_id,
                available=candidate.available,
                unavailable_reason=candidate.unavailable_reason,
                check=(
                    None
                    if candidate.violations is None
                    else _build_check_result(schedule_version_id, candidate.violations)
                ),
                block_members=(
                    None
                    if candidate.block_members is None
                    else [
                        PlacedLessonDetail(
                            lesson_id=member.lesson_id, to_time_slot_id=member.time_slot_id
                        )
                        for member in candidate.block_members
                    ]
                ),
            )
            for candidate in outcome.candidates
        ],
    )


@router.post(
    "/{schedule_version_id}/place-lesson",
    response_model=PlaceLessonResult,
    dependencies=[Depends(require_version_in_school)],
)
def place_lesson(
    schedule_version_id: int,
    placement: PlaceLessonRequest,
    db: Session = Depends(get_db),
) -> PlaceLessonResult:
    outcome = lesson_placement_service.place_lesson(
        db,
        schedule_version_id,
        placement.lesson_id,
        placement.time_slot_id,
        placement.teacher_id,
        placement.room_id,
        dry_run=placement.dry_run,
    )
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return PlaceLessonResult(
        schedule_version_id=schedule_version_id,
        dry_run=placement.dry_run,
        changes=[PlacementChangeDetail.model_validate(change) for change in outcome.changes],
        check=_build_check_result(schedule_version_id, outcome.violations),
    )


# --- Task 95: change the room of scheduled lessons (decision 32) ---
# Locked timetable / row of another record / inactive room (409) and a
# missing row or room (404) are converted by main.py's handlers.


@router.post(
    "/{schedule_version_id}/change-room",
    response_model=ChangeRoomResult,
    dependencies=[Depends(require_version_in_school)],
)
def change_room(
    schedule_version_id: int,
    request: ChangeRoomRequest,
    db: Session = Depends(get_db),
) -> ChangeRoomResult:
    outcome = room_change_service.change_room(
        db,
        schedule_version_id,
        request.schedule_id,
        request.room_id,
        request.scope,
        dry_run=request.dry_run,
    )
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
    return ChangeRoomResult(
        schedule_version_id=schedule_version_id,
        dry_run=request.dry_run,
        scope=request.scope,
        changes=[RoomChangeDetail.model_validate(change) for change in outcome.changes],
        check=_build_check_result(schedule_version_id, outcome.violations),
    )
