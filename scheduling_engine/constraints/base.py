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
