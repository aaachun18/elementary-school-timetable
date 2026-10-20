from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.school import School

# User.role values. Task 98 (the wizard redesign) split the old ADMIN into
# two: ADMIN is now the 系統管理員 (schools and accounts, not bound to any
# school) and COORDINATOR the 教學組長 (one school's scheduling data and
# its teacher accounts).
ADMIN = "ADMIN"
COORDINATOR = "COORDINATOR"
TEACHER = "TEACHER"
ROLES = (ADMIN, COORDINATOR, TEACHER)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'COORDINATOR', 'TEACHER')", name="ck_users_role_valid"
        ),
        # Task 98: a 系統管理員 belongs to no school; every other account
        # belongs to exactly one.
        CheckConstraint(
            "(role = 'ADMIN') = (school_id IS NULL)",
            name="ck_users_school_matches_role",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"))

    school: Mapped["School | None"] = relationship()
