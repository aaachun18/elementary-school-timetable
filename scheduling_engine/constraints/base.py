"""Shared base for every Hard/Soft Constraint. Framework-independent: no
SQLAlchemy, no FastAPI (see AGENTS.md section 4)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from scheduling_engine.models.domain import LessonAssignment


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass
class ConstraintViolation:
    """One concrete violation found by a constraint. Field set matches
    AGENTS.md section 8 (Conflict Explanation) so callers always know why
    a schedule failed and, where possible, what to do about it."""

    type: str
    severity: Severity
    lesson_id: int | None
    teacher_id: int | None
    class_id: int | None
    subject_id: int | None
    time_slot_id: int | None
    message: str
    suggested_action: str | None = None
    room_id: int | None = None
    class_subject_requirement_id: int | None = None
    # Task 88: lesson blocks (連堂) -- which block of the requirement.
    block_no: int | None = None
    # Task 88: a stable "which problem is this" key, the same before and
    # after a move as long as the problem itself is the same one (it never
    # contains a time slot). Set by the newer violation types only; None
    # means the caller decides identity from the ids (the frontend's
    # violationIdentityKey()).
    identity_key: str | None = None
    # Task 88: the stored Schedule row the violation's lesson sits in. The
    # engine knows nothing about Schedule rows and never sets this; the
    # schedule check (backend services/schedule_check.py) fills it in.
    schedule_id: int | None = None


class BaseConstraint(ABC):
    """Subclasses implement explain_violations() only. validate() is
    derived from it (not a separate implementation) so the two can never
    disagree with each other -- there is exactly one source of truth for
    what counts as a violation."""

    @abstractmethod
    def explain_violations(
        self, assignments: list[LessonAssignment]
    ) -> list[ConstraintViolation]:
        """Return every violation found in `assignments`. Empty list means
        no violations."""

    def validate(self, assignments: list[LessonAssignment]) -> bool:
        """True if `assignments` has no violations of this constraint."""
        return not self.explain_violations(assignments)
