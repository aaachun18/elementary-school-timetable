"""Task 87: a requirement's lesson pattern (連堂樣式), e.g. "2+1" -- the
weekly_periods split into blocks of consecutive lessons. Each block is
taught on one day, in adjacent teaching periods, by one teacher in one
room; different blocks of the same requirement go on different days.

Pure functions, shared by the request schemas (validation), the
requirement service (weekly_periods consistency) and generate-lessons
(assigning each Lesson its block).

Normalisation: the blocks are sorted largest first ("1+2" -> "2+1"), so
one pattern always has one spelling and block 1 is always the longest
block. Spaces are ignored; an empty pattern means "no pattern".
"""

import re
from typing import Protocol

MIN_BLOCK_SIZE = 1
MAX_BLOCK_SIZE = 3

_PATTERN_RE = re.compile(r"^\d+(\+\d+)*$")

FORMAT_MESSAGE = "連堂樣式格式不正確，請以加號分隔 1 到 3 的數字，例如 2+1"
BLOCK_SIZE_MESSAGE = "連堂樣式每一組的節數必須介於 1 到 3"
TOTAL_MESSAGE = "連堂樣式的節數總和必須等於每週節數"


def parse_lesson_pattern(pattern: str) -> tuple[int, ...]:
    """The block sizes, largest first. Raises ValueError (with a Chinese
    message) for anything that isn't digits joined by "+", or a block
    outside 1-3."""
    compact = pattern.replace(" ", "")
    if not _PATTERN_RE.match(compact):
        raise ValueError(FORMAT_MESSAGE)
    sizes = [int(part) for part in compact.split("+")]
    if any(size < MIN_BLOCK_SIZE or size > MAX_BLOCK_SIZE for size in sizes):
        raise ValueError(BLOCK_SIZE_MESSAGE)
    return tuple(sorted(sizes, reverse=True))


def normalize_lesson_pattern(pattern: str | None) -> str | None:
    """None / blank -> None; otherwise the canonical spelling ("1+2" ->
    "2+1"). Raises ValueError like parse_lesson_pattern()."""
    if pattern is None or pattern.strip() == "":
        return None
    return "+".join(str(size) for size in parse_lesson_pattern(pattern))


def check_pattern_total(pattern: str | None, weekly_periods: int) -> None:
    """A pattern's blocks must add up to weekly_periods exactly. Raises
    ValueError otherwise; no pattern is always fine."""
    if pattern is None:
        return
    if sum(parse_lesson_pattern(pattern)) != weekly_periods:
        raise ValueError(TOTAL_MESSAGE)


def block_positions(pattern: str | None, lesson_count: int) -> list[tuple[int | None, int | None]]:
    """(block_no, block_seq) for the lessons with sequence_number 1..
    lesson_count, in order: lessons fill block 1 first, then block 2, and
    so on (both numbered from 1). Without a pattern, or for a lesson past
    the pattern's total, both are None."""
    if pattern is None:
        return [(None, None)] * lesson_count
    positions: list[tuple[int | None, int | None]] = []
    for block_no, size in enumerate(parse_lesson_pattern(pattern), start=1):
        positions.extend((block_no, block_seq) for block_seq in range(1, size + 1))
    positions = positions[:lesson_count]
    positions.extend([(None, None)] * (lesson_count - len(positions)))
    return positions


class BlockFields(Protocol):
    """What assign_block_fields() reads and writes (a Lesson)."""

    sequence_number: int
    block_no: int | None
    block_seq: int | None


def assign_block_fields(lessons: "list[BlockFields]", pattern: str | None) -> bool:
    """Sets block_no / block_seq on a requirement's lessons from its
    pattern, by sequence_number order (see block_positions()). Used by
    generate-lessons and whenever a requirement's pattern changes, so the
    lessons always mirror the pattern. Returns whether anything changed."""
    ordered = sorted(lessons, key=lambda lesson: lesson.sequence_number)
    changed = False
    for lesson, (block_no, block_seq) in zip(ordered, block_positions(pattern, len(ordered))):
        if lesson.block_no != block_no or lesson.block_seq != block_seq:
            lesson.block_no = block_no
            lesson.block_seq = block_seq
            changed = True
    return changed
