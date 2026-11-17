import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict

# Password rule shared by every password: register, the managers' reset
# (PasswordReset) and 個人資料's own change. The upper bound is bcrypt's own input limit, which is
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


# 帳號改版: 教學組長 / 一般老師 accounts are their email. A simple shape
# check only (something@domain.tld) -- whether it really receives mail is
# shown by the account mail itself. Stored lower case.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EMAIL_MAX_LENGTH = 100
EMAIL_FORMAT_MESSAGE = "Email 格式不正確"


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) > EMAIL_MAX_LENGTH or not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError(EMAIL_FORMAT_MESSAGE)
    return normalized


Email = Annotated[str, AfterValidator(normalize_email)]

TEACHER_NAME_MAX_LENGTH = 100
NAME_REQUIRED_MESSAGE = "請填寫名字"
NAME_TOO_LONG_MESSAGE = "名字最多 100 個字"


def normalize_person_name(value: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError(NAME_REQUIRED_MESSAGE)
    if len(normalized) > TEACHER_NAME_MAX_LENGTH:
        raise ValueError(NAME_TOO_LONG_MESSAGE)
    return normalized


PersonName = Annotated[str, AfterValidator(normalize_person_name)]

UserRole = Literal["ADMIN", "COORDINATOR", "TEACHER"]


class AdminBootstrap(BaseModel):
    """Body of POST /api/v1/auth/register: only the very first account of
    an empty system (always a 系統管理員) is created this way."""

    username: str
    password: Password


class AccountCreate(BaseModel):
    """Body of POST /api/v1/users/ (帳號改版). The account is the email
    and the password is generated and mailed.

    - 系統管理員: creates a 教學組長 -- school_id required, no name (the
      教學組長 fills it in on 個人資料).
    - 教學組長: creates an 一般老師 of their own school -- teacher_name
      required, school_id ignored."""

    email: Email
    school_id: int | None = None
    teacher_name: PersonName | None = None


class UserUpdate(BaseModel):
    """Body of PATCH /api/v1/users/{id}, 系統管理員 only: is_active (停用 /
    啟用) and school_id (所屬學校; for an 一般老師 None = 無所屬學校)."""

    is_active: bool | None = None
    school_id: int | None = None


class UserListItem(BaseModel):
    """One row of GET /api/v1/users -- never hashed_password."""

    id: int
    username: str
    role: UserRole
    is_active: bool
    school_id: int | None
    # The account's teacher name (its current teacher row, or for an
    # 一般老師 with no school the latest one).
    teacher_name: str | None = None
    # The account's current teacher row; None while it has no school.
    teacher_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class AccountCreated(BaseModel):
    """Response of POST /api/v1/users/. initial_password is only returned
    when the mail could not be sent, so the creator can pass it on."""

    user: UserListItem
    email_sent: bool
    initial_password: str | None = None


class UsernameAvailability(BaseModel):
    """GET /api/v1/users/username-available: whether a new account may
    take this email (accounts are unique across every school)."""

    available: bool


class PasswordReset(BaseModel):
    """Body of PATCH /api/v1/users/{id}/password (a manager resets someone
    else's password). Same rule as every other password."""

    password: Password


class UserRead(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool
    school_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- 個人資料維護 (GET / PATCH /api/v1/me) ---


class ProfileRead(BaseModel):
    username: str
    role: UserRole
    school_id: int | None
    school_name: str | None
    # 教學組長 / 一般老師 only; None for the 系統管理員.
    name: str | None


class ProfileUpdate(BaseModel):
    name: PersonName


class OwnPasswordChange(BaseModel):
    current_password: str
    new_password: Password
