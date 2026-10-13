from psycopg.errors import (
    CheckViolation,
    ForeignKeyViolation,
    NotNullViolation,
    UniqueViolation,
)
from sqlalchemy.exc import IntegrityError


class DependentRecordsExistError(Exception):
    """Raised by a delete_xxx() service function when the row cannot be
    deleted because other tables still hold a foreign key reference to it.
    """


class InvalidReferenceError(Exception):
    """Raised by a create/update service function when a foreign key column
    (e.g. grade_id) points at a row that does not exist.
    """


class DuplicateValueError(Exception):
    """Raised by a create/update service function when a value violates a
    UNIQUE constraint (e.g. duplicate Subject.name) or a CHECK constraint
    (e.g. Teacher.min_weekly_periods > max_weekly_periods).
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


class PublishedVersionImmutableError(Exception):
    """Raised when a call would modify a PUBLISHED ScheduleVersion, or a
    Schedule row belonging to one: updating the version itself (including
    changing its status away from PUBLISHED), generate-lessons, run-
    scheduler, or updating/deleting one of its Schedule rows.

    A PUBLISHED version is the authoritative, in-use timetable -- the spec
    requires it to be fully locked; the only sanctioned way to change
    anything is to create a new DRAFT version first (Task 62:
    POST /schedule-versions/{id}/copy).
    """


class RequirementUsedByPublishedScheduleError(Exception):
    """Raised by delete_class_subject_requirement() when one or more of the
    requirement's Lesson rows are referenced by a Schedule row under a
    PUBLISHED ScheduleVersion.

    Task 56: deleting a requirement normally takes its Lesson rows (and
    their DRAFT Schedule rows) with it, but a PUBLISHED timetable is fully
    locked -- removing a lesson it actually uses would silently alter it.
    Kept separate from DependentRecordsExistError so the caller gets a
    specific reason instead of the generic "still referenced" message.
    """


class CannotDeleteSelfError(Exception):
    """Raised by delete_user() when an ADMIN tries to delete the account
    they are currently logged in as.

    Task 59: this rule alone guarantees at least one ADMIN always remains
    -- only an ADMIN can delete accounts, and never their own, so the one
    doing the deleting always survives. Without that guarantee, an empty
    users table would reopen anonymous first-ADMIN registration (Task 57).
    """


class ScheduleVersionAlreadyScheduledError(Exception):
    """Raised by run_scheduler() when the target ScheduleVersion already has
    one or more Schedule rows.

    Consistent with LessonOverProvisionedError's "never auto-discard data"
    philosophy: re-running the scheduler must not silently overwrite an
    existing result (which might be a manually-tweaked or already-published
    schedule). The caller must explicitly delete the existing Schedule rows
    first (via the existing DELETE /api/v1/schedules/{id} endpoint) before
    running the scheduler again.
    """


class TargetSemesterNotFoundError(Exception):
    """Raised by copy_schedule_version() (Task 62) when target_semester_id
    points at a Semester that does not exist. Its own exception (-> 404)
    rather than the router's usual "service returned None" 404, because
    None already means "the SOURCE version doesn't exist" for that call.
    """


class CopyAcrossAcademicYearsError(Exception):
    """Raised by copy_schedule_version() (Task 62) when the target semester
    belongs to a different AcademicYear than the source version's semester.

    Class has no semester column, so a class is the same row in every
    semester of every year -- copying across years would put last year's
    classes (which have since moved up a grade) into next year's
    timetable, and the current model cannot express that promotion.
    """


class TargetSemesterHasRequirementsError(Exception):
    """Raised by copy_schedule_version() (Task 62) when a cross-semester
    copy targets a semester that already has ClassSubjectRequirement rows.

    Requirements and Lessons are per-semester and shared by every version
    in that semester; merging a copied set into an existing one would
    either duplicate (class, subject) pairs or silently change what the
    target semester's existing versions point at. Refused instead, before
    anything is written.
    """


class CopySourceInconsistentError(Exception):
    """Raised by copy_schedule_version() (Task 62) when a Schedule row of
    the source version points at a Lesson that is not under the source
    semester's requirements -- the database doesn't enforce that a
    version's Schedule rows belong to its own semester, and such a row has
    no new Lesson to be remapped to. The whole copy is aborted rather than
    silently dropping the row.
    """


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
        raise DuplicateValueError(
            "This value conflicts with an existing record or violates a "
            "data rule."
        ) from exc
    raise exc
