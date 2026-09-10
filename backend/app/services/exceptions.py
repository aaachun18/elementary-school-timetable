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
    """

    def __init__(self, over_provisioned: list[dict[str, int]]) -> None:
        self.over_provisioned = over_provisioned
        super().__init__(
            f"{len(over_provisioned)} requirement(s) already have more "
            "lessons than their weekly_periods calls for."
        )


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
