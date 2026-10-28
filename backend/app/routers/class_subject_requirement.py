from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    coordinator_school_id,
    member_school_id,
    require_school_member,
)
from app.database import get_db
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.user import User
from app.schemas.class_subject_requirement import (
    ClassSubjectRequirementCreate,
    ClassSubjectRequirementRead,
    ClassSubjectRequirementUpdate,
    LessonPatternBatch,
    RequirementSyncRequest,
    RequirementSyncResult,
)
from app.services import class_subject_requirement as requirement_service
from app.services import schedule_version as schedule_version_service

# Task 73: every Read field except is_locked comes straight from the row.
_COLUMN_FIELDS = tuple(
    field for field in ClassSubjectRequirementRead.model_fields if field != "is_locked"
)


def _to_read(
    requirement: ClassSubjectRequirement, *, is_locked: bool
) -> ClassSubjectRequirementRead:
    return ClassSubjectRequirementRead(
        **{field: getattr(requirement, field) for field in _COLUMN_FIELDS},
        is_locked=is_locked,
    )


def _to_read_one(
    db: Session, requirement: ClassSubjectRequirement
) -> ClassSubjectRequirementRead:
    return _to_read(
        requirement,
        is_locked=schedule_version_service.settings_locked_for_requirement(db, requirement),
    )


router = APIRouter(
    prefix="/api/v1/class-subject-requirements",
    tags=["class_subject_requirements"],
    dependencies=[Depends(require_school_member)],
)


@router.post(
    "/",
    response_model=ClassSubjectRequirementRead,
    status_code=status.HTTP_201_CREATED,
)
def create_class_subject_requirement(
    requirement_data: ClassSubjectRequirementCreate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> ClassSubjectRequirementRead:
    requirement = requirement_service.create_class_subject_requirement(
        db, requirement_data, school_id=school_id
    )
    return _to_read_one(db, requirement)


@router.post("/sync", response_model=RequirementSyncResult)
def sync_class_subject_requirements(
    data: RequirementSyncRequest,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> RequirementSyncResult:
    """The wizard's 科目需求 step: the record's requirements follow the
    school's 科目需求 (學校資料) -- see sync_version_requirements()."""
    result = requirement_service.sync_version_requirements(
        db, data.schedule_version_id, school_id=school_id
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ScheduleVersion not found"
        )
    return result


@router.get("/", response_model=list[ClassSubjectRequirementRead])
def list_class_subject_requirements(
    skip: int = 0,
    limit: int = 100,
    schedule_version_id: int | None = None,
    current_user: User = Depends(require_school_member),
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> list[ClassSubjectRequirementRead]:
    # Task 72: a TEACHER only sees requirements of published records -- a
    # silent filter, same as /schedules (Task 43).
    requirements = requirement_service.get_class_subject_requirements(
        db,
        skip=skip,
        limit=limit,
        schedule_version_id=schedule_version_id,
        role=current_user.role,
        school_id=school_id,
    )
    return [_to_read_one(db, requirement) for requirement in requirements]


@router.get("/{requirement_id}", response_model=ClassSubjectRequirementRead)
def get_class_subject_requirement(
    requirement_id: int,
    current_user: User = Depends(require_school_member),
    db: Session = Depends(get_db),
    school_id: int = Depends(member_school_id),
) -> ClassSubjectRequirementRead:
    # Task 72: a hidden requirement is the same 404 as a missing one.
    requirement = requirement_service.get_class_subject_requirement(
        db, requirement_id, role=current_user.role,
        school_id=school_id,
    )
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ClassSubjectRequirement not found",
        )
    return _to_read_one(db, requirement)


# Declared before PATCH /{requirement_id}, so "lesson-patterns" is never
# read as an id.
@router.patch("/lesson-patterns", response_model=list[ClassSubjectRequirementRead])
def update_lesson_patterns(
    data: LessonPatternBatch,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> list[ClassSubjectRequirementRead]:
    """Task 103: several requirements' 連堂樣式 at once, in one transaction
    -- the wizard's 「複製此連堂設定至所有同年級班級」."""
    requirements = requirement_service.update_lesson_patterns(
        db, data.items, school_id=school_id
    )
    if requirements is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ClassSubjectRequirement not found",
        )
    return [_to_read_one(db, requirement) for requirement in requirements]


@router.patch("/{requirement_id}", response_model=ClassSubjectRequirementRead)
def update_class_subject_requirement(
    requirement_id: int,
    requirement_data: ClassSubjectRequirementUpdate,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> ClassSubjectRequirementRead:
    requirement = requirement_service.update_class_subject_requirement(
        db, requirement_id, requirement_data, school_id=school_id
    )
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ClassSubjectRequirement not found",
        )
    return _to_read_one(db, requirement)


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class_subject_requirement(
    requirement_id: int,
    db: Session = Depends(get_db),
    school_id: int = Depends(coordinator_school_id),
) -> None:
    deleted = requirement_service.delete_class_subject_requirement(
        db, requirement_id, school_id=school_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ClassSubjectRequirement not found",
        )
