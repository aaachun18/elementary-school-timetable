"""帳號改版: 個人資料維護 -- what any logged-in account may see and change
about itself (GET / PATCH /api/v1/me, PATCH /api/v1/me/password)."""

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.school import School
from app.models.user import ADMIN, User
from app.schemas.user import ProfileRead
from app.services.exceptions import AccountPermissionError, AccountStateError
from app.services.user import current_teacher_of, latest_teacher_of

ADMIN_HAS_NO_NAME_MESSAGE = "系統管理員帳號沒有名字可以修改"
NO_SCHOOL_NAME_MESSAGE = "目前無所屬學校，無法修改名字，請聯絡系統管理員"
WRONG_CURRENT_PASSWORD_MESSAGE = "目前密碼不正確"


def get_profile(db: Session, user: User) -> ProfileRead:
    school = db.get(School, user.school_id) if user.school_id is not None else None
    teacher = latest_teacher_of(db, user.id) if user.role != ADMIN else None
    return ProfileRead.model_validate(
        {
            "username": user.username,
            "role": user.role,
            "school_id": user.school_id,
            "school_name": school.name if school is not None else None,
            "name": teacher.name if teacher is not None else None,
        }
    )


def update_name(db: Session, user: User, name: str) -> ProfileRead:
    """A 教學組長 / 一般老師 renames their current teacher row (what their
    timetables show)."""
    if user.role == ADMIN:
        raise AccountPermissionError(ADMIN_HAS_NO_NAME_MESSAGE)
    teacher = current_teacher_of(db, user.id)
    if teacher is None:
        raise AccountStateError(NO_SCHOOL_NAME_MESSAGE)
    teacher.name = name
    db.commit()
    return get_profile(db, user)


def change_own_password(
    db: Session, user: User, current_password: str, new_password: str
) -> None:
    """個人資料's 重設密碼: needs the current password."""
    if not verify_password(current_password, user.hashed_password):
        raise AccountStateError(WRONG_CURRENT_PASSWORD_MESSAGE)
    user.hashed_password = hash_password(new_password)
    db.commit()
