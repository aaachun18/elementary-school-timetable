from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.academic_year import Semester

# ScheduleVersion.status values (v3) -- what the record is, as 排課紀錄
# shows it:
# - NOT_SCHEDULED (尚未排課): settings only, no timetable yet. The only
#   status whose settings may change, and the only one 自動排課 runs on.
# - AUTO (自動排課): the scheduler built its timetable.
# - MANUAL (手動排課): saved from a manual edit.
# - COPIED (複製自編號 x): a copy of another record's timetable
#   (copied_from_number = x).
# - EDITING: the hidden working copy a manual edit changes; 儲存課表 turns
#   it into a record (or writes it back), leaving the page throws it away.
#   Never listed, never published, no number.
# Publishing is not a status: is_published marks the semester's one
# published record, which keeps (and returns to) its own status.
NOT_SCHEDULED = "NOT_SCHEDULED"
AUTO = "AUTO"
MANUAL = "MANUAL"
COPIED = "COPIED"
EDITING = "EDITING"
STATUSES = (NOT_SCHEDULED, AUTO, MANUAL, COPIED, EDITING)
# Records with a finished timetable: they can be published, copied and
# manually edited.
TIMETABLE_STATUSES = frozenset({AUTO, MANUAL, COPIED})

NOTE_MAX_LENGTH = 200


class ScheduleVersion(TimestampMixin, Base):
    """v3: one 排課紀錄 -- a semester's scheduling settings (who teaches,
    their weekly ranges and unavailable slots, each grade's open slots, the
    class subject requirements and their lessons; every settings table
    points here) and, once scheduled, its timetable (Schedule rows). Each
    record owns its own copy of all of it, so changing one never changes
    another."""

    __tablename__ = "schedule_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('NOT_SCHEDULED', 'AUTO', 'MANUAL', 'COPIED', 'EDITING')",
            name="ck_schedule_versions_status_valid",
        ),
        # A working copy has no number; every record has one.
        CheckConstraint(
            "(status = 'EDITING') = (version_number IS NULL)",
            name="ck_schedule_versions_number_unless_editing",
        ),
        CheckConstraint(
            "(status = 'EDITING') = (editing_source_id IS NOT NULL)",
            name="ck_schedule_versions_editing_source",
        ),
        CheckConstraint(
            "(status = 'COPIED') = (copied_from_number IS NOT NULL)",
            name="ck_schedule_versions_copied_from",
        ),
        CheckConstraint(
            "NOT is_published OR status IN ('AUTO', 'MANUAL', 'COPIED')",
            name="ck_schedule_versions_published_has_timetable",
        ),
        # 排課紀錄's 編號: one sequence per school, never reused.
        UniqueConstraint(
            "school_id", "version_number", name="uq_schedule_versions_school_number"
        ),
        # At most one published record per semester, guaranteed by the
        # database itself, not only by the publish service.
        Index(
            "uq_schedule_versions_one_published_per_semester",
            "semester_id",
            unique=True,
            postgresql_where=text("is_published"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # The school the record (and its number) belongs to -- always the
    # semester's own school.
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    # 排課紀錄's 編號 (1, 2, 3 ... per school, oldest first). None only for
    # an EDITING working copy.
    version_number: Mapped[int | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(20))
    is_published: Mapped[bool] = mapped_column(default=False, server_default="false")
    # COPIED: the 編號 of the record it was copied from (kept as a number,
    # so it still reads right after that record is deleted).
    copied_from_number: Mapped[int | None] = mapped_column()
    # EDITING: the record this working copy edits.
    editing_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedule_versions.id")
    )
    # 備註, e.g. 「王老師上三年級自然課版」.
    note: Mapped[str | None] = mapped_column(String(NOTE_MAX_LENGTH))

    semester: Mapped["Semester"] = relationship()
