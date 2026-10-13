from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.exceptions import (
    CannotDeleteSelfError,
    DependentRecordsExistError,
    raise_for_integrity_error,
)


def create_user(db: Session, user_data: UserCreate) -> User:
    user = User(
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(user)
    return user


def lock_users_and_check_empty(db: Session) -> bool:
    """Task 57: returns True if the users table has no rows at all.

    Takes a PostgreSQL table lock first, held until this session's
    transaction ends (the commit inside create_user(), or the rollback when
    the session closes after a 401/403). SHARE ROW EXCLUSIVE conflicts with
    itself and with INSERT, so two concurrent register calls are serialized:
    the second one only counts after the first has committed (or rolled
    back), and can never also see an empty table and create a second
    anonymous ADMIN. Plain reads (e.g. login's SELECT) are not blocked.
    """
    db.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
    user_count = db.scalar(select(func.count()).select_from(User))
    return user_count == 0


def get_user_by_username(db: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return db.scalars(stmt).first()


# --- Task 59: account management (ADMIN only, see routers/users.py) ---


def get_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())


def reset_password(db: Session, user_id: int, new_password: str) -> bool:
    """Returns False if the user doesn't exist (caller should 404)."""
    user = db.get(User, user_id)
    if user is None:
        return False

    user.hashed_password = hash_password(new_password)
    db.commit()
    return True


def delete_user(db: Session, user_id: int, current_user_id: int) -> bool:
    """Returns False if the user doesn't exist (caller should 404).

    Raises CannotDeleteSelfError when user_id is the caller's own account
    -- checked before anything is staged, so the account is never touched.
    """
    user = db.get(User, user_id)
    if user is None:
        return False

    if user.id == current_user_id:
        raise CannotDeleteSelfError(
            f"User {user_id} is the currently logged-in account and cannot "
            "delete itself."
        )

    db.delete(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # No table references users.id today; kept for the same reason
        # every other delete_xxx() has it -- a future FK must surface as a
        # clear 409, not an unhandled 500.
        db.rollback()
        raise DependentRecordsExistError(
            f"User {user_id} cannot be deleted: other records still "
            "reference it."
        ) from exc

    return True
