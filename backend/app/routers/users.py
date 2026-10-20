from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin, require_manager
from app.database import get_db
from app.models.user import User
from app.schemas.user import PasswordReset, UserListItem, UserUpdate
from app.services import user as user_service

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
    return [
        UserListItem.model_validate(user).model_copy(update={"teacher_name": teacher_name})
        for user, teacher_name in user_service.get_users(db, current_user)
    ]


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
    return UserListItem.model_validate(user).model_copy(
        update={"teacher_name": user_service.get_teacher_name(db, user.id)}
    )


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
