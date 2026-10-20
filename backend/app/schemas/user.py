from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

# Password rule shared by register (UserCreate) and the ADMIN password reset
# (PasswordReset). The upper bound is bcrypt's own input limit, which is
# 72 BYTES, not characters: bcrypt 4.0.x (what passlib uses here) silently
# truncates anything longer, so two different long passwords sharing the
# same first 72 bytes would both log in. Counting UTF-8 bytes rejects that
# instead of truncating -- for ASCII passwords bytes == characters, while
# e.g. a Chinese character takes 3 bytes. The lower bound counts
# characters.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_BYTES = 72

PASSWORD_TOO_SHORT_MESSAGE = "密碼至少需要 8 個字元"
PASSWORD_TOO_LONG_MESSAGE = "密碼太長，請縮短（中文等非英數字元每字會佔用較多長度）"


def validate_password(password: str) -> str:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(PASSWORD_TOO_SHORT_MESSAGE)
    if (
        len(password) > PASSWORD_MAX_BYTES
        or len(password.encode("utf-8")) > PASSWORD_MAX_BYTES
    ):
        raise ValueError(PASSWORD_TOO_LONG_MESSAGE)
    return password


Password = Annotated[str, AfterValidator(validate_password)]


UserRole = Literal["ADMIN", "COORDINATOR", "TEACHER"]

TEACHER_NAME_REQUIRED_MESSAGE = "建立一般老師帳號時必須填寫教師姓名"


class UserBase(BaseModel):
    username: str
    role: UserRole


class UserCreate(UserBase):
    """Task 98: school_id is required for a COORDINATOR or TEACHER account
    created by the 系統管理員; a 教學組長 may leave it out (their own school
    is used). teacher_name is required for a TEACHER account -- creating
    the account also creates its Teacher with this name."""

    password: Password
    school_id: int | None = None
    teacher_name: str | None = None

    @model_validator(mode="after")
    def _teacher_needs_name(self) -> "UserCreate":
        if self.role == "TEACHER" and (
            self.teacher_name is None or self.teacher_name.strip() == ""
        ):
            raise ValueError(TEACHER_NAME_REQUIRED_MESSAGE)
        return self


class UserUpdate(BaseModel):
    """Task 98: body of PATCH /api/v1/users/{id}. is_active (停用 / 啟用)
    may be changed by the 系統管理員 or, for their own school's teachers,
    the 教學組長; school_id (綁定學校) only by the 系統管理員."""

    is_active: bool | None = None
    school_id: int | None = None


class UserListItem(UserBase):
    """Task 59: one row of GET /api/v1/users -- never hashed_password.
    Task 98 added is_active, school_id and the TEACHER account's teacher
    name for the account-management page."""

    id: int
    is_active: bool
    school_id: int | None
    teacher_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PasswordReset(BaseModel):
    """Task 59: body of PATCH /api/v1/users/{id}/password. Same validation
    as UserCreate.password (the shared Password rule above), so resetting
    a password can never accept something register itself would reject."""

    password: Password


class UserRead(UserBase):
    id: int
    is_active: bool
    school_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
