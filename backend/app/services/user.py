from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.teacher import Teacher
from app.models.user import ADMIN, COORDINATOR, TEACHER, User
from app.schemas.user import UserCreate, UserUpdate
from app.services.exceptions import (
    AccountPermissionError,
    CannotDeleteSelfError,
    DependentRecordsExistError,
    raise_for_integrity_error,
)
from app.services.teacher_periods import (
    ACCOUNT_DEFAULT_MAX_WEEKLY_PERIODS,
    ACCOUNT_DEFAULT_MIN_WEEKLY_PERIODS,
)

# --- Task 98: who may manage which accounts ---
#
# 系統管理員 (ADMIN): every account, every school.
# 教學組長 (COORDINATOR): only TEACHER accounts of their own school.
# 一般老師 (TEACHER): none (the routers already refuse them with 403).

COORDINATOR_ROLE_MESSAGE = "教學組長只能建立一般老師帳號"
COORDINATOR_SCHOOL_MESSAGE = "教學組長只能管理自己學校的帳號"
SCHOOL_BINDING_MESSAGE = "只有系統管理員可以變更帳號所屬的學校"
SCHOOL_REQUIRED_MESSAGE = "教學組長與一般老師帳號必須指定所屬學校"
ADMIN_HAS_NO_SCHOOL_MESSAGE = "系統管理員帳號不屬於任何學校"
DEACTIVATE_SELF_MESSAGE = "不能停用目前登入中的帳號"


def _resolve_new_account_school(actor: User | None, user_data: UserCreate) -> int | None:
    """The school_id the new account gets, or AccountPermissionError.
    actor None = the anonymous bootstrap of the very first account."""
    if user_data.role == ADMIN:
        if user_data.school_id is not None:
            raise AccountPermissionError(ADMIN_HAS_NO_SCHOOL_MESSAGE)
        if actor is not None and actor.role != ADMIN:
            raise AccountPermissionError(COORDINATOR_ROLE_MESSAGE)
        return None

    if actor is not None and actor.role == COORDINATOR:
        if user_data.role != TEACHER:
            raise AccountPermissionError(COORDINATOR_ROLE_MESSAGE)
        if user_data.school_id not in (None, actor.school_id):
            raise AccountPermissionError(COORDINATOR_SCHOOL_MESSAGE)
        return actor.school_id

    if user_data.school_id is None:
        raise AccountPermissionError(SCHOOL_REQUIRED_MESSAGE)
    return user_data.school_id


def create_user(db: Session, user_data: UserCreate, actor: User | None = None) -> User:
    """Creates the account and, for a TEACHER account, its Teacher in the
    same transaction (one to one). `actor` is the logged-in account doing
    it; None only for the anonymous bootstrap of the first ADMIN."""
    school_id = _resolve_new_account_school(actor, user_data)
    user = User(
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
        is_active=True,
        school_id=school_id,
    )
    db.add(user)
    try:
        db.flush()
        if user_data.role == TEACHER and user_data.teacher_name is not None:
            # UserCreate guarantees teacher_name for a TEACHER account (and
            # _resolve_new_account_school() a school for it).
            assert school_id is not None
            db.add(
                Teacher(
                    school_id=school_id,
                    name=user_data.teacher_name.strip(),
                    is_active=True,
                    min_weekly_periods=ACCOUNT_DEFAULT_MIN_WEEKLY_PERIODS,
                    max_weekly_periods=ACCOUNT_DEFAULT_MAX_WEEKLY_PERIODS,
                    user_id=user.id,
                )
            )
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


# --- Task 59: account management (see routers/users.py) ---


def _is_visible_to(actor: User, user: User) -> bool:
    """Task 98: a 教學組長 only sees their own school's TEACHER accounts;
    anything else is reported as not found (404), never a separate 403 --
    same stance as a TEACHER's read scope (Task 72)."""
    if actor.role == ADMIN:
        return True
    return user.role == TEACHER and user.school_id == actor.school_id


def _get_visible_user(db: Session, user_id: int, actor: User) -> User | None:
    user = db.get(User, user_id)
    if user is None or not _is_visible_to(actor, user):
        return None
    return user


def _teacher_of(db: Session, user_id: int) -> Teacher | None:
    return db.scalars(select(Teacher).where(Teacher.user_id == user_id)).first()


def get_teacher_name(db: Session, user_id: int) -> str | None:
    return db.scalars(select(Teacher.name).where(Teacher.user_id == user_id)).first()


def get_users(db: Session, actor: User) -> list[tuple[User, str | None]]:
    """Every account the actor may manage, each with its Teacher's name
    (None for a non-TEACHER account, or a TEACHER one without a Teacher)."""
    stmt = (
        select(User, Teacher.name)
        .outerjoin(Teacher, Teacher.user_id == User.id)
        .order_by(User.id)
    )
    if actor.role != ADMIN:
        stmt = stmt.where(User.role == TEACHER, User.school_id == actor.school_id)
    return [(user, teacher_name) for user, teacher_name in db.execute(stmt).all()]


def update_user(
    db: Session, user_id: int, user_data: UserUpdate, actor: User
) -> User | None:
    """Task 98: 停用 / 啟用 and (ADMIN only) 綁定學校. Returns None if the
    user doesn't exist or isn't visible to the actor (caller should 404).
    Deactivating a TEACHER account also deactivates its Teacher, so it
    drops out of every new schedule's teacher list."""
    user = _get_visible_user(db, user_id, actor)
    if user is None:
        return None

    changes = user_data.model_dump(exclude_unset=True)
    if "school_id" in changes:
        if actor.role != ADMIN:
            raise AccountPermissionError(SCHOOL_BINDING_MESSAGE)
        if user.role == ADMIN and changes["school_id"] is not None:
            raise AccountPermissionError(ADMIN_HAS_NO_SCHOOL_MESSAGE)
        if user.role != ADMIN and changes["school_id"] is None:
            raise AccountPermissionError(SCHOOL_REQUIRED_MESSAGE)
        user.school_id = changes["school_id"]
        # The account's Teacher moves with it. Its existing schedules stay
        # where they are, in the old school's semesters.
        teacher = _teacher_of(db, user.id)
        if teacher is not None and changes["school_id"] is not None:
            teacher.school_id = changes["school_id"]

    if changes.get("is_active") is not None:
        if user.id == actor.id and not changes["is_active"]:
            raise AccountPermissionError(DEACTIVATE_SELF_MESSAGE)
        user.is_active = changes["is_active"]
        teacher = _teacher_of(db, user.id)
        if teacher is not None:
            teacher.is_active = changes["is_active"]

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(user)
    return user


def reset_password(db: Session, user_id: int, new_password: str, actor: User) -> bool:
    """Returns False if the user doesn't exist or isn't visible to the
    actor (caller should 404)."""
    user = _get_visible_user(db, user_id, actor)
    if user is None:
        return False

    user.hashed_password = hash_password(new_password)
    db.commit()
    return True


def delete_user(db: Session, user_id: int, current_user_id: int) -> bool:
    """Returns False if the user doesn't exist (caller should 404).

    Raises CannotDeleteSelfError when user_id is the caller's own account
    -- checked before anything is staged, so the account is never touched.
    Task 98: a TEACHER account with its Teacher is referenced by it, so it
    surfaces as DependentRecordsExistError -- such accounts are 停用, not
    deleted.
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
        db.rollback()
        raise DependentRecordsExistError(
            f"User {user_id} cannot be deleted: other records still "
            "reference it."
        ) from exc

    return True
