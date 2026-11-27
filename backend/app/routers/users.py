from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_manager
from app.database import get_db
from app.models.user import User
from app.schemas.deactivation import DeactivationImpactRead
from app.schemas.user import (
    AccountCreate,
    AccountCreated,
    PasswordReset,
    UserListItem,
    UsernameAvailability,
    UserUpdate,
)
from app.services import user as user_service
from app.services.deactivation import DeactivationImpact

# 帳號管理, for the 系統管理員 and the 教學組長. Which accounts each may
# create, see and change is the service's job (services/user.py); anything
# the actor may not see is 404. AccountPermissionError (403) and
# DuplicateValueError (409, the email is taken) are converted by the global
# handlers in main.py. Accounts are never deleted.
router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
    dependencies=[Depends(require_manager)],
)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.get("/", response_model=list[UserListItem])
def list_users(
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> list[UserListItem]:
    """`search`: only the accounts whose 帳號 or 教師姓名 contains it."""
    return user_service.get_users(db, current_user, search)


@router.post("/", response_model=AccountCreated, status_code=status.HTTP_201_CREATED)
def create_account(
    data: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> AccountCreated:
    """系統管理員 -> 教學組長, 教學組長 -> 一般老師; the password is
    generated and mailed."""
    return user_service.create_account(db, data, current_user)


# 新增帳號 checks the email while it is typed, before 儲存.
@router.get("/username-available", response_model=UsernameAvailability)
def check_username_available(
    username: str, db: Session = Depends(get_db)
) -> UsernameAvailability:
    return UsernameAvailability(available=not user_service.is_username_taken(db, username))


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


@router.post("/{user_id}/leave-school", response_model=UserListItem)
def leave_school(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> UserListItem:
    """教學組長's 離校 of one of their school's 一般老師."""
    user = user_service.leave_school(db, user_id, current_user)
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
