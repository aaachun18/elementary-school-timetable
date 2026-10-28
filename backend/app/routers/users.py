from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin, require_manager
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    PasswordReset,
    SameNameTeacher,
    TeacherNationalIdUpdate,
    UserListItem,
    UsernameAvailability,
    UserUpdate,
)
from app.schemas.deactivation import DeactivationImpactRead
from app.services import user as user_service
from app.services.deactivation import DeactivationImpact

# Task 59: account management for the frontend's 帳號管理 page. Creating an
# account is deliberately NOT duplicated here -- it stays POST
# /api/v1/auth/register (Task 57).
#
# Task 98: open to the 系統管理員 and the 教學組長. Which accounts each may
# see and change is the service's job (a 教學組長: only their own school's
# teacher accounts, anything else 404); deleting stays ADMIN-only -- a
# 教學組長 only 停用s.
router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
    dependencies=[Depends(require_manager)],
)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.get("/", response_model=list[UserListItem])
def list_users(
    db: Session = Depends(get_db), current_user: User = Depends(require_manager)
) -> list[UserListItem]:
    return user_service.get_users(db, current_user)


# 新增帳號 checks the 帳號名稱 while it is typed, before 儲存.
@router.get("/username-available", response_model=UsernameAvailability)
def check_username_available(
    username: str, db: Session = Depends(get_db)
) -> UsernameAvailability:
    return UsernameAvailability(available=not user_service.is_username_taken(db, username))


# 帳號管理 asks for a 身分證字號 when the school already has a teacher of
# the name being entered (and then for the earlier one's, if missing).
@router.get("/same-name-teachers", response_model=list[SameNameTeacher])
def list_same_name_teachers(
    name: str,
    school_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> list[SameNameTeacher]:
    return user_service.find_same_name_teachers(db, current_user, name, school_id)


# DuplicateValueError (the number is another teacher's of the school) and
# DuplicateTeacherNameError (clearing it while the name is shared) are
# converted to 409 / 422 by the global handlers in main.py.
@router.patch("/teachers/{teacher_id}/national-id", response_model=SameNameTeacher)
def set_teacher_national_id(
    teacher_id: int,
    data: TeacherNationalIdUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> SameNameTeacher:
    teacher = user_service.set_teacher_national_id(
        db, teacher_id, data.national_id, current_user
    )
    if teacher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    return teacher


# AccountPermissionError is intentionally not caught here -- the global
# exception handler in main.py converts it to 403.
@router.patch("/{user_id}", response_model=UserListItem)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> UserListItem:
    user = user_service.update_user(db, user_id, user_data, current_user)
    if user is None:
        raise _not_found()
    return user_service.get_user_list_item(db, user)


@router.get("/{user_id}/deactivation-impact", response_model=DeactivationImpactRead)
def user_deactivation_impact(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> DeactivationImpact:
    impact = user_service.account_deactivation_impact(db, user_id, current_user)
    if impact is None:
        raise _not_found()
    return impact


@router.patch("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(
    user_id: int,
    password_data: PasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> None:
    updated = user_service.reset_password(
        db, user_id, password_data.password, current_user
    )
    if not updated:
        raise _not_found()


# CannotDeleteSelfError is intentionally not caught here -- the global
# exception handler in main.py converts it to 409.
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    deleted = user_service.delete_user(db, user_id, current_user.id)
    if not deleted:
        raise _not_found()
