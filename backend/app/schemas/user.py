from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict

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


class UserBase(BaseModel):
    username: str
    role: Literal["ADMIN", "TEACHER"]


class UserCreate(UserBase):
    password: Password


class UserListItem(UserBase):
    """Task 59: one row of GET /api/v1/users -- deliberately only id,
    username and role (never hashed_password, nor anything else the
    account-management page doesn't need)."""

    id: int

    model_config = ConfigDict(from_attributes=True)


class PasswordReset(BaseModel):
    """Task 59: body of PATCH /api/v1/users/{id}/password. Same validation
    as UserCreate.password (the shared Password rule above), so resetting
    a password can never accept something register itself would reject."""

    password: Password


class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
