from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.teacher import Teacher
from app.models.user import ADMIN, COORDINATOR, TEACHER, User
from app.schemas.user import AccountCreate, AccountCreated, UserListItem, UserUpdate
from app.services import mailer
from app.services.deactivation import DeactivationImpact, deactivation_impact
from app.services.exceptions import AccountPermissionError, raise_for_integrity_error
from app.services.password_generator import generate_initial_password
from app.services.teacher_periods import (
    ACCOUNT_DEFAULT_MAX_WEEKLY_PERIODS,
    ACCOUNT_DEFAULT_MIN_WEEKLY_PERIODS,
)

# --- who may manage which accounts (帳號改版) ---
#
# 系統管理員 (ADMIN): creates 教學組長 accounts only; sees and manages every
#   教學組長 / 一般老師 account (never 系統管理員 accounts, not even its
#   own): 停用 / 啟用, 重設密碼, 所屬學校 (including assigning an 一般老師
#   with no school).
# 教學組長 (COORDINATOR): creates 一般老師 accounts of their own school;
#   sees only those, and may only 重設密碼 and 離校.
# 一般老師 (TEACHER): none (the routers already refuse them with 403).
# No account is ever deleted.

ADMIN_CREATES_COORDINATOR_ONLY_MESSAGE = "系統管理員只能建立教學組長帳號"
COORDINATOR_ROLE_MESSAGE = "教學組長只能建立一般老師帳號"
SCHOOL_BINDING_MESSAGE = "只有系統管理員可以變更帳號所屬的學校"
ACTIVATION_MESSAGE = "只有系統管理員可以停用或啟用帳號"
SCHOOL_REQUIRED_MESSAGE = "教學組長帳號必須指定所屬學校"
TEACHER_NAME_REQUIRED_MESSAGE = "請填寫教師姓名"
DEACTIVATE_SELF_MESSAGE = "不能停用目前登入中的帳號"
LEAVE_SCHOOL_MESSAGE = "只有教學組長可以把老師設為離校"


# --- the very first account ---


def lock_users_and_check_empty(db: Session) -> bool:
    """Task 57: returns True if the users table has no rows at all.

    Takes a PostgreSQL table lock first, held until this session's
    transaction ends (the commit inside create_bootstrap_admin(), or the
    rollback when the session closes after a 403). SHARE ROW EXCLUSIVE
    conflicts with itself and with INSERT, so two concurrent register calls
    are serialized: the second one only counts after the first has
    committed (or rolled back), and can never also see an empty table and
    create a second anonymous ADMIN. Plain reads (e.g. login's SELECT) are
    not blocked.
    """
    db.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
    user_count = db.scalar(select(func.count()).select_from(User))
    return user_count == 0


def create_bootstrap_admin(db: Session, username: str, password: str) -> User:
    """The first 系統管理員 of an empty system (POST /auth/register, and
    the seed script)."""
    user = User(
        username=username.strip(),
        hashed_password=hash_password(password),
        role=ADMIN,
        is_active=True,
        school_id=None,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return db.scalars(stmt).first()


# --- teacher rows of an account ---


def current_teacher_of(db: Session, user_id: int) -> Teacher | None:
    """The account's teacher row in its current school (not left), if any."""
    stmt = select(Teacher).where(Teacher.user_id == user_id, Teacher.has_left.is_(False))
    return db.scalars(stmt).first()


def latest_teacher_of(db: Session, user_id: int) -> Teacher | None:
    """The account's current teacher row, else the newest one it left."""
    current = current_teacher_of(db, user_id)
    if current is not None:
        return current
    stmt = select(Teacher).where(Teacher.user_id == user_id).order_by(Teacher.id.desc())
    return db.scalars(stmt).first()


def _new_teacher(school_id: int, name: str, user: User) -> Teacher:
    return Teacher(
        school_id=school_id,
        name=name,
        is_active=user.is_active,
        min_weekly_periods=ACCOUNT_DEFAULT_MIN_WEEKLY_PERIODS,
        max_weekly_periods=ACCOUNT_DEFAULT_MAX_WEEKLY_PERIODS,
        user_id=user.id,
        has_left=False,
    )


def _leave_current_school(db: Session, user: User) -> Teacher | None:
    """Marks the account's current teacher row as left (kept for old
    timetables, out of scheduling) and returns it."""
    current = current_teacher_of(db, user.id)
    if current is not None:
        current.has_left = True
        current.is_active = False
        # The partial unique index allows only one row that has not left:
        # write this one before another row comes back.
        db.flush()
    return current


def _join_school(db: Session, user: User, school_id: int, name: str) -> None:
    """Gives the account a current teacher row in `school_id`: the row it
    left there before, if any (back to the old school), else a new one."""
    stmt = (
        select(Teacher)
        .where(Teacher.user_id == user.id, Teacher.school_id == school_id)
        .order_by(Teacher.id.desc())
    )
    previous = db.scalars(stmt).first()
    if previous is not None:
        previous.has_left = False
        previous.is_active = user.is_active
    else:
        db.add(_new_teacher(school_id, name, user))


def _move_to_school(db: Session, user: User, school_id: int | None) -> None:
    """The account changes school (None = 無所屬學校, 一般老師 only)."""
    if user.school_id == school_id:
        return
    latest = latest_teacher_of(db, user.id)
    name = latest.name if latest is not None else _email_name(user.username)
    _leave_current_school(db, user)
    user.school_id = school_id
    if school_id is not None:
        _join_school(db, user, school_id, name)


def _email_name(email: str) -> str:
    """The name a new 教學組長 starts with until they fill in their own on
    個人資料: the part of the email before @."""
    return email.split("@", 1)[0]


# --- 新增帳號 ---


def _new_account_role_school_name(
    actor: User, data: AccountCreate
) -> tuple[str, int, str]:
    """(role, school_id, teacher name) of the account `actor` creates, or
    AccountPermissionError."""
    if actor.role == ADMIN:
        if data.school_id is None:
            raise AccountPermissionError(SCHOOL_REQUIRED_MESSAGE)
        return COORDINATOR, data.school_id, _email_name(data.email)
    if actor.role == COORDINATOR:
        assert actor.school_id is not None  # the users CHECK guarantees it
        if data.teacher_name is None:
            raise AccountPermissionError(TEACHER_NAME_REQUIRED_MESSAGE)
        return TEACHER, actor.school_id, data.teacher_name
    raise AccountPermissionError(COORDINATOR_ROLE_MESSAGE)


def create_account(db: Session, data: AccountCreate, actor: User) -> AccountCreated:
    """Creates the account (帳號 = email, a random 8 character password)
    with its teacher row, then mails the email and password. The account
    stays even if the mail fails -- the password is then returned so the
    creator can pass it on."""
    role, school_id, teacher_name = _new_account_role_school_name(actor, data)
    password = generate_initial_password()
    user = User(
        username=data.email,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
        school_id=school_id,
    )
    db.add(user)
    try:
        db.flush()
        db.add(_new_teacher(school_id, teacher_name, user))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
    db.refresh(user)

    email_sent = mailer.send_account_created_email(user.username, password)
    return AccountCreated(
        user=get_user_list_item(db, user),
        email_sent=email_sent,
        initial_password=None if email_sent else password,
    )


# --- 帳號管理 list ---


def _is_visible_to(actor: User, user: User) -> bool:
    """A 系統管理員 sees every 教學組長 / 一般老師 account; a 教學組長
    only their own school's 一般老師 accounts. Anything else is reported as
    not found (404), never a separate 403 -- same stance as a TEACHER's
    read scope (Task 72)."""
    if actor.role == ADMIN:
        return user.role != ADMIN
    return user.role == TEACHER and user.school_id == actor.school_id


def _get_visible_user(db: Session, user_id: int, actor: User) -> User | None:
    user = db.get(User, user_id)
    if user is None or not _is_visible_to(actor, user):
        return None
    return user


def is_username_taken(db: Session, username: str) -> bool:
    """Accounts are unique across every school (users.username)."""
    return get_user_by_username(db, username.strip().lower()) is not None


def _list_item(user: User, current: Teacher | None, latest: Teacher | None) -> UserListItem:
    item = UserListItem.model_validate(user)
    return item.model_copy(
        update={
            "teacher_name": latest.name if latest is not None else None,
            "teacher_id": current.id if current is not None else None,
        }
    )


def get_users(db: Session, actor: User, search: str | None = None) -> list[UserListItem]:
    """Every account the actor may manage, with its teacher name. With
    `search`, only the accounts whose 帳號 or 教師姓名 contains it
    (ignoring case)."""
    stmt = select(User).order_by(User.id)
    if actor.role == ADMIN:
        stmt = stmt.where(User.role != ADMIN)
    else:
        stmt = stmt.where(User.role == TEACHER, User.school_id == actor.school_id)
    needle = (search or "").strip()
    if needle != "":
        name_match = select(Teacher.user_id).where(
            Teacher.user_id.is_not(None),
            Teacher.name.icontains(needle, autoescape=True),
        )
        stmt = stmt.where(
            or_(
                User.username.icontains(needle, autoescape=True),
                User.id.in_(name_match),
            )
        )
    users = list(db.scalars(stmt).all())
    teachers_by_user = _teachers_by_user(db, [user.id for user in users])
    return [_list_item_from_rows(user, teachers_by_user.get(user.id, [])) for user in users]


def _teachers_by_user(db: Session, user_ids: list[int]) -> dict[int, list[Teacher]]:
    """Each account's teacher rows, newest first."""
    if not user_ids:
        return {}
    stmt = select(Teacher).where(Teacher.user_id.in_(user_ids)).order_by(Teacher.id.desc())
    rows: dict[int, list[Teacher]] = {}
    for teacher in db.scalars(stmt).all():
        assert teacher.user_id is not None
        rows.setdefault(teacher.user_id, []).append(teacher)
    return rows


def _list_item_from_rows(user: User, teachers: list[Teacher]) -> UserListItem:
    current = next((teacher for teacher in teachers if not teacher.has_left), None)
    latest = current if current is not None else (teachers[0] if teachers else None)
    return _list_item(user, current, latest)


def get_user_list_item(db: Session, user: User) -> UserListItem:
    """One row of get_users(), e.g. after an update."""
    return _list_item(user, current_teacher_of(db, user.id), latest_teacher_of(db, user.id))


# --- 停用 / 啟用, 所屬學校, 離校, 重設密碼 ---


def account_deactivation_impact(
    db: Session, user_id: int, actor: User
) -> DeactivationImpact | None:
    """What 停用 of the account touches: its current teacher row's records.
    None if the actor can't see the account (caller should 404)."""
    user = _get_visible_user(db, user_id, actor)
    if user is None:
        return None
    teacher = current_teacher_of(db, user.id)
    if teacher is None:
        return DeactivationImpact(0, 0, 0, 0)
    return deactivation_impact(db, "teacher", teacher.id)


def update_user(
    db: Session, user_id: int, user_data: UserUpdate, actor: User
) -> User | None:
    """系統管理員 only: 停用 / 啟用 and 所屬學校. Returns None if the user
    doesn't exist or isn't visible to the actor (caller should 404).

    Changing the school leaves the old school's teacher row behind (marked
    left, still showing in old timetables) and gives the account a teacher
    row in the new one. Deactivating also deactivates the current teacher
    row, so it drops out of every new schedule's teacher list."""
    user = _get_visible_user(db, user_id, actor)
    if user is None:
        return None

    changes = user_data.model_dump(exclude_unset=True)
    if "school_id" in changes:
        if actor.role != ADMIN:
            raise AccountPermissionError(SCHOOL_BINDING_MESSAGE)
        if user.role == COORDINATOR and changes["school_id"] is None:
            raise AccountPermissionError(SCHOOL_REQUIRED_MESSAGE)
        _move_to_school(db, user, changes["school_id"])

    if changes.get("is_active") is not None:
        if actor.role != ADMIN:
            raise AccountPermissionError(ACTIVATION_MESSAGE)
        if user.id == actor.id and not changes["is_active"]:
            raise AccountPermissionError(DEACTIVATE_SELF_MESSAGE)
        user.is_active = changes["is_active"]
        teacher = current_teacher_of(db, user.id)
        if teacher is not None:
            teacher.is_active = changes["is_active"]

    _commit(db)
    db.refresh(user)
    return user


def leave_school(db: Session, user_id: int, actor: User) -> User | None:
    """教學組長's 離校: their school's 一般老師 becomes 無所屬學校 until the
    系統管理員 assigns a school. The teacher row stays in this school
    (old timetables keep the name) but is out of scheduling. Returns None
    if the account isn't one of the actor's school's teachers (404)."""
    if actor.role != COORDINATOR:
        raise AccountPermissionError(LEAVE_SCHOOL_MESSAGE)
    user = _get_visible_user(db, user_id, actor)
    if user is None:
        return None
    _move_to_school(db, user, None)
    _commit(db)
    db.refresh(user)
    return user


def reset_password(db: Session, user_id: int, new_password: str, actor: User) -> bool:
    """A manager sets someone else's password. Returns False if the user
    doesn't exist or isn't visible to the actor (caller should 404)."""
    user = _get_visible_user(db, user_id, actor)
    if user is None:
        return False

    user.hashed_password = hash_password(new_password)
    db.commit()
    return True


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_for_integrity_error(exc)
