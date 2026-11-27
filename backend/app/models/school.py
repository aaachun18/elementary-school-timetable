from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class School(TimestampMixin, Base):
    __tablename__ = "schools"
    __table_args__ = (
        CheckConstraint(
            "school_type IN ('ELEMENTARY', 'JUNIOR_HIGH', 'SENIOR_HIGH')",
            name="ck_schools_school_type_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True)
    # 國小 / 國中 / 高中 (app/services/school_structure.py SchoolType): fixes
    # the school's grades and time slot grid, both built when the school is
    # created. Not changeable afterwards.
    school_type: Mapped[str] = mapped_column(
        String(20), default="ELEMENTARY", server_default="ELEMENTARY"
    )
