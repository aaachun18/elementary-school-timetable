from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_access_token
from app.database import get_db
from app.models.schedule_version import ScheduleVersion
from app.models.user import ADMIN, COORDINATOR, TEACHER, User
from app.services.school_scope import is_in_school
from app.services.user import get_user_by_username

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
# Task 57: same Bearer-token parsing as oauth2_scheme, but a missing
# Authorization header yields None instead of an automatic 401 -- for the
# one endpoint (register) that must accept anonymous calls in one case
# (empty users table) and require ADMIN in every other case.
optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", auto_error=False
)


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = decode_access_token(token)
    except InvalidTokenError as exc:
        raise _credentials_exception() from exc

    username = payload.get("sub")
    if not isinstance(username, str):
        raise _credentials_exception()

    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise _credentials_exception()
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires ADMIN role",
        )
    return current_user


# Task 98: the 系統管理員 (ADMIN) or a 教學組長 (COORDINATOR) -- the
# accounts that manage accounts (app/routers/users.py, auth register).
MANAGER_ROLES = frozenset({ADMIN, COORDINATOR})
# Task 98: the accounts that belong to a school and work with its
# scheduling data. The 系統管理員 only manages schools and accounts, so
# every scheduling endpoint refuses it.
SCHOOL_MEMBER_ROLES = frozenset({COORDINATOR, TEACHER})


def require_manager(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in MANAGER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires ADMIN or COORDINATOR role",
        )
    return current_user


def require_school_member(current_user: User = Depends(get_current_user)) -> User:
    """Task 98: reading a school's scheduling data -- a 教學組長 or 一般老師."""
    if current_user.role not in SCHOOL_MEMBER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires a school account",
        )
    return current_user


def require_coordinator(current_user: User = Depends(get_current_user)) -> User:
    """Task 98: changing a school's scheduling data -- a 教學組長 only."""
    if current_user.role != COORDINATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires COORDINATOR role",
        )
    return current_user


def _school_of(user: User) -> int:
    # The users table's CHECK guarantees a school for every non-ADMIN
    # account, and both callers below have already refused ADMIN.
    if user.school_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires a school account",
        )
    return user.school_id


def member_school_id(current_user: User = Depends(require_school_member)) -> int:
    """The school whose data a read endpoint returns."""
    return _school_of(current_user)


def coordinator_school_id(current_user: User = Depends(require_coordinator)) -> int:
    """The school whose data a write endpoint changes."""
    return _school_of(current_user)


def require_version_in_school(
    schedule_version_id: int,
    school_id: int = Depends(coordinator_school_id),
    db: Session = Depends(get_db),
) -> None:
    """Task 98: the gate for every /schedule-versions/{id}/... action (copy,
    generate-lessons, run-scheduler, check, adjustments): a version of
    another school is the same 404 as one that doesn't exist. The services
    behind these endpoints then take the school from the version itself
    (school_scope.school_id_of_version) for every teacher, room and time
    slot they look up."""
    if not is_in_school(db, ScheduleVersion, schedule_version_id, school_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleVersion not found",
        )
