from psycopg.errors import (
    CheckViolation,
    ForeignKeyViolation,
    NotNullViolation,
    UniqueViolation,
)
from sqlalchemy.exc import IntegrityError

from app.services.integrity_messages import integrity_violation_message


class DependentRecordsExistError(Exception):
    """Raised by a delete_xxx() service function when the row cannot be
    deleted because other tables still hold a foreign key reference to it.

    `steps` (optional) is what to do first, in order, so the delete can
    succeed -- Chinese sentences from services/delete_guidance.py, shown
    behind the error's ? icon.
    """

    def __init__(self, message: str, steps: list[str] | None = None) -> None:
        self.steps = steps or []
        super().__init__(message)


class ClassInUseError(DependentRecordsExistError):
    """A class used by 排課紀錄 can't be deleted (-> 409, code
    CLASS_IN_USE, with how many records use it): deactivate it instead."""

    def __init__(self, message: str, record_count: int, steps: list[str] | None = None) -> None:
        self.record_count = record_count
        super().__init__(message, steps)


class AccountPermissionError(Exception):
    """Task 98: the logged-in account may not create / change this account
    the way it asked (-> 403), e.g. a 教學組長 creating a 教學組長, or
    binding a teacher to another school. The message is Chinese text for
    the user."""


class DuplicateTeacherNameError(Exception):
    """A new teacher account has the same name as a teacher already in the
    school, but no 身分證字號 to tell them apart (-> 422). The message is
    Chinese text for the user."""


class InvalidReferenceError(Exception):
    """Raised by a create/update service function when a foreign key column
    (e.g. grade_id) points at a row that does not exist.
    """


class InvalidLessonPatternError(Exception):
    """Task 87: a requirement's lesson_pattern doesn't add up to its
    weekly_periods after an update (-> 422). The message is the Chinese
    text from app/services/lesson_pattern.py."""


class SchoolStructureViolationError(Exception):
    """A value the school's fixed structure doesn't allow (-> 422): a class
    name that isn't one of its grade's options, a non-schedulable time slot
    opened for a grade, a grade or subject of the requirement's own school
    rules ... The message is Chinese text for the user."""


class InvalidTeacherPeriodsError(Exception):
    """Task 88: a teacher update would leave min_weekly_periods above
    max_weekly_periods (-> 422). The message is the Chinese text from
    app/services/teacher_periods.py."""


class BlockAdjustmentRefusedError(Exception):
    """Task 89: a move or swap the lesson block (連堂) rules don't allow
    (-> 409). `reason` is the code from app/services/block_adjustment.py
    (BLOCK_OUT_OF_RANGE / BLOCK_TARGET_OCCUPIED / BLOCK_SWAP_UNSUPPORTED),
    the same one move-candidates reports for that target."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class PlacementRefusedError(Exception):
    """Task 92: placing an unscheduled lesson is refused (-> 409). `reason`
    is TEACHER_REQUIRED (no teacher in the request and none required by
    the requirement) or one of the codes from plan_place() in
    app/services/block_adjustment.py -- the same one place-candidates
    reports for that target."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class LessonNotInVersionError(Exception):
    """Task 92: the lesson to place belongs to another record's
    requirements (-> 409)."""


class LessonAlreadyScheduledError(Exception):
    """Task 92: the lesson to place already has a Schedule row in the
    version -- it is moved with move-lesson instead (-> 409)."""


class DuplicateValueError(Exception):
    """Raised by a create/update service function when a value violates a
    UNIQUE constraint (e.g. duplicate Subject.name) or a CHECK constraint
    (e.g. Teacher.min_weekly_periods > max_weekly_periods). The message is
    the Chinese sentence for the user (services/integrity_messages.py).
    """


class LessonOverProvisionedError(Exception):
    """Raised by generate_lessons() when one or more ClassSubjectRequirement
    rows already have MORE Lesson rows than their weekly_periods calls for.

    generate_lessons() must never auto-delete the excess (that's a business
    rule, not a technicality), so when this is raised the whole call is
    aborted -- nothing is created for ANY requirement in that call, not
    just the over-provisioned ones -- so the caller sees one clear, atomic
    outcome: either the sync fully happened, or nothing did and here's
    what's wrong.

    Task 28: each entry also reports whether the specific Lesson rows that
    would be "the excess" (highest sequence_number first) include any with
    a manually-set fixed_time_slot_id -- those must never be silently
    treated as deletable candidates, so the caller needs to know they
    require manual handling.
    """

    def __init__(self, over_provisioned: list[dict[str, int | bool | list[int]]]) -> None:
        self.over_provisioned = over_provisioned
        super().__init__(
            f"{len(over_provisioned)} requirement(s) already have more "
            "lessons than their weekly_periods calls for."
        )


class SettingsLockedError(Exception):
    """v3: a call would change the settings (teachers, grade slots,
    requirements, lessons) of a 排課紀錄 that is no longer 尚未排課 -- only a
    NOT_SCHEDULED record's settings change; any other record keeps the
    settings its timetable was made under. To change them, copy the
    settings into a new record (-> 409)."""


class TimetableLockedError(Exception):
    """v3: a call would change the timetable (Schedule rows) of a record
    that is not a manual edit's working copy (EDITING). A saved timetable
    never changes in place: 手動編輯課表 starts a working copy, and 儲存課表
    turns it into a record (-> 409)."""


class PublishedVersionDeleteError(Exception):
    """Task 80 / v3: raised by delete_schedule_version() for the
    semester's published record -- the live timetable cannot simply
    disappear (-> 409)."""


class RecordStatusError(Exception):
    """v3: an action the record's status doesn't allow (-> 409) --
    publishing or editing a record with no timetable, saving something that
    is not a working copy, reassigning a teacher outside a copied
    timetable. `message` is the Chinese sentence the user reads."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class CannotDeleteSelfError(Exception):
    """Raised by delete_user() when an ADMIN tries to delete the account
    they are currently logged in as.

    Task 59: this rule alone guarantees at least one ADMIN always remains
    -- only an ADMIN can delete accounts, and never their own, so the one
    doing the deleting always survives. Without that guarantee, an empty
    users table would reopen anonymous first-ADMIN registration (Task 57).
    """


class ScheduleVersionAlreadyScheduledError(Exception):
    """Raised by run_scheduler() when the record is not 尚未排課 (or somehow
    already has Schedule rows): 自動排課 only ever fills an empty record,
    never overwrites a timetable (-> 409). To schedule again, copy the
    record's settings into a new one."""


class TargetSemesterNotFoundError(Exception):
    """Raised by copy_timetable() (Task 62 / v3) when target_semester_id
    points at a Semester that does not exist. Its own exception (-> 404)
    rather than the router's usual "service returned None" 404, because
    None already means "the SOURCE record doesn't exist" for that call.
    """


class CopyAcrossAcademicYearsError(Exception):
    """Raised by copy_timetable() (Task 62 / v3) when the target semester
    belongs to a different AcademicYear than the source version's semester.

    Class has no semester column, so a class is the same row in every
    semester of every year -- copying across years would put last year's
    classes (which have since moved up a grade) into next year's
    timetable, and the current model cannot express that promotion.
    """


class CopySourceInconsistentError(Exception):
    """Raised when copying a record (Task 62 / v3) finds a Schedule row of
    the source pointing at a Lesson that is not under the source's own
    requirements -- the database doesn't enforce that, and such a row has
    no copied Lesson to be remapped to. The whole copy is aborted rather
    than silently dropping the row.
    """


class TargetRecordNotFoundError(Exception):
    """A record named in a version-level operation's request body does not
    exist (-> 404). Base for the operation-specific subclasses below.

    Carries the exact same English `detail` the corresponding router's own
    404 already uses (e.g. "Teacher not found", "Schedule not found"), so
    the frontend's existing translation table keeps working. A separate
    exception rather than "service returns None", because None already
    means "the ScheduleVersion doesn't exist" for these calls.
    """

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class ReassignmentTargetNotFoundError(TargetRecordNotFoundError):
    """Raised by reassign_teacher() (Task 63) when the requested
    ClassSubjectRequirement or new Teacher does not exist (-> 404)."""


class AdjustmentTargetNotFoundError(TargetRecordNotFoundError):
    """Raised by move_lesson()/swap_lessons() (Task 65) when a requested
    Schedule row, target TimeSlot or target Room does not exist (-> 404)."""


class ScheduleNotInVersionError(Exception):
    """Raised by move_lesson()/swap_lessons() (Task 65) when a Schedule row
    exists but belongs to a different ScheduleVersion than the one in the
    URL -- moving it would silently edit another (possibly locked)
    version."""


class CannotSwapWithSelfError(Exception):
    """Raised by swap_lessons() (Task 65) when both ids name the same
    Schedule row."""


class RequirementNotInVersionError(Exception):
    """Raised by reassign_teacher() (Task 63) when the requirement belongs to
    another record than the one being edited -- none of its Lessons can be
    in this timetable, and setting its required_teacher_id would silently
    change another record's settings (-> 409).
    """


class InactiveRoomAssignmentError(Exception):
    """Raised by change_room() (Task 95) when the new room's is_active is
    False (-> 409) -- the same stance as an inactive teacher for
    reassign-teacher: every other room problem (type, double-booking) is
    reported by the check instead."""


class InactiveTeacherAssignmentError(Exception):
    """Raised by reassign_teacher() (Task 63) when the new teacher's
    is_active is False. Every other rule (qualification, availability,
    workload, double-booking) is reported by the schedule check instead of
    blocking; assigning someone already deactivated is never a sensible
    manual adjustment, so this one is refused up front.
    """


class CombinedLessonRuleError(Exception):
    """共同排課: a combined lesson that breaks one of its rules
    (services/combined_lesson.py) -> 422 with the Chinese message."""


class CombinedLessonInUseError(Exception):
    """共同排課: a change to a requirement that is in a combined lesson and
    would break it (its lesson pattern) -> 409 with the Chinese message."""


def raise_for_integrity_error(exc: IntegrityError) -> None:
    """Classify a SQLAlchemy IntegrityError raised during create/update into
    one of our domain-specific exceptions above, and raise it.

    Classification is based on the *type* of the underlying psycopg error
    (exc.orig), which psycopg maps 1:1 from PostgreSQL's SQLSTATE error
    codes -- see https://www.postgresql.org/docs/current/errcodes-appendix.html.
    This is not string-matching against error messages: it's an isinstance
    check against psycopg's own typed exception hierarchy, so it does not
    depend on message wording/locale and won't silently misclassify.

    Covers four SQLSTATE cases:
    - 23503 ForeignKeyViolation -> InvalidReferenceError
    - 23505 UniqueViolation     -> DuplicateValueError
    - 23514 CheckViolation      -> DuplicateValueError
    - 23502 NotNullViolation    -> DuplicateValueError (a required column
      was left out/null; grouped with Unique/Check as "violates a data
      rule" rather than getting its own exception class, since it's not a
      distinct case any caller needs to react to differently)

    Always raises (never returns normally). An IntegrityError shape we don't
    recognise is re-raised as-is rather than guessed at, so it surfaces as a
    500 instead of being silently mislabeled.

    Note: this function is for create/update only. delete_xxx() should keep
    raising DependentRecordsExistError directly for any IntegrityError,
    since a DELETE can only fail this way (a child row blocking it) -- it
    can never be a unique/check violation.
    """
    orig = exc.orig
    if isinstance(orig, ForeignKeyViolation):
        raise InvalidReferenceError(
            "One or more referenced records do not exist."
        ) from exc
    if isinstance(orig, (UniqueViolation, CheckViolation, NotNullViolation)):
        # The message names what is wrong (身分證字號重複, 帳號名稱已被使用
        # ...), from the violated constraint's name.
        raise DuplicateValueError(integrity_violation_message(orig)) from exc
    raise exc
