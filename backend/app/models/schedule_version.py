from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ColumnElement,
    ForeignKey,
    Index,
    ScalarSelect,
    String,
    UniqueConstraint,
    case,
    exists,
    func,
    null,
    select,
    text,
)
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

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
        CheckConstraint(
            "wizard_furthest_step IS NULL OR wizard_furthest_step >= 0",
            name="ck_schedule_versions_wizard_furthest_step_non_negative",
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
    # The record's permanent serial (1, 2, 3 ... per school, oldest first;
    # see display_number below for the 編號 people see). None only for an
    # EDITING working copy.
    version_number: Mapped[int | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(20))
    is_published: Mapped[bool] = mapped_column(default=False, server_default="false")
    # COPIED: the serial (version_number) of the record it was copied from;
    # copied_from_display_number below turns it into that record's current
    # 編號.
    copied_from_number: Mapped[int | None] = mapped_column()
    # EDITING: the record this working copy edits.
    editing_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedule_versions.id")
    )
    # 備註, e.g. 「王老師上三年級自然課版」.
    note: Mapped[str | None] = mapped_column(String(NOTE_MAX_LENGTH))
    # Task 103: the furthest 開始排課 step reached (the step's index in the
    # wizard, 0 = 選擇學期) -- every step up to it stays clickable in the
    # step row. Only ever goes up (update_schedule_version). None: not
    # recorded yet (records made before Task 103).
    wizard_furthest_step: Mapped[int | None] = mapped_column()

    semester: Mapped["Semester"] = relationship()


# --- 編號 as 排課紀錄 shows it ---
#
# version_number is the record's permanent serial (1, 2, 3 ... per school,
# in the order the records were made) and is what copied_from_number points
# at. What people see is display_number instead: 1 is the school's newest
# record, 2 the one before it, and so on -- it shifts by one every time a
# record is made or deleted. Both are read-only SQL expressions computed when
# the record is loaded (no column of their own); a working copy (no
# version_number) has neither.
# The table itself, not aliased(ScheduleVersion): an ORM alias would
# configure every mapper while the models are still being imported.
_other = ScheduleVersion.__table__.alias("other_records")


def _records_from(serial: ColumnElement[int | None]) -> ScalarSelect[int]:
    """How many of the school's records have a serial >= `serial` -- the
    display number of the record whose serial that is."""
    return (
        select(func.count())
        .where(
            _other.c.school_id == ScheduleVersion.school_id,
            _other.c.version_number >= serial,
        )
        .correlate_except(_other)
        .scalar_subquery()
    )


ScheduleVersion.display_number = column_property(
    case(
        (ScheduleVersion.version_number.is_(None), null()),
        else_=_records_from(ScheduleVersion.version_number),
    )
)
# COPIED: the source record's display number now -- None once that record
# has been deleted (the copy then says only that it is a copy).
ScheduleVersion.copied_from_display_number = column_property(
    case(
        (
            exists().where(
                _other.c.school_id == ScheduleVersion.school_id,
                _other.c.version_number == ScheduleVersion.copied_from_number,
            ),
            _records_from(ScheduleVersion.copied_from_number),
        ),
        else_=null(),
    )
)
