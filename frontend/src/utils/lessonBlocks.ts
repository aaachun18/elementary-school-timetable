// Task 90: lesson blocks (連堂) on the timetable grid -- which lessons
// belong together (selected / dragged as one) and which cells show the
// connecting bar. Pure functions, no React.
//
// A block of two or more lessons is a group. A lesson in no block, or in a
// block of one lesson (the "1" of "2+1"), is a group of its own -- the
// backend moves it exactly like a single lesson (Task 89), so the grid
// treats it like one too.

export interface BlockLesson {
  scheduleId: number;
  requirementId: number;
  blockNo: number | null;
  blockSeq: number | null;
  // How many lessons the block has (0 for a lesson in no block).
  blockSize: number;
  weekday: number;
  period: number;
}

// null for a lesson that moves on its own.
export function blockGroupKey(lesson: BlockLesson): string | null {
  if (lesson.blockNo === null || lesson.blockSize < 2) {
    return null;
  }
  return `${lesson.requirementId}:${lesson.blockNo}`;
}

// The schedule ids that move together with `lesson` (itself included).
export function blockGroupMemberIds(
  schedules: readonly BlockLesson[],
  lesson: BlockLesson,
): ReadonlySet<number> {
  const key = blockGroupKey(lesson);
  if (key === null) {
    return new Set([lesson.scheduleId]);
  }
  return new Set(
    schedules.filter((other) => blockGroupKey(other) === key).map((other) => other.scheduleId),
  );
}

// Which side of a block lesson's cell joins the next lesson of the same
// block: `above` -- the block's previous lesson is in the period right
// above, same day; `below` likewise. A split block's lessons are still
// marked as block lessons, just not joined.
export interface BlockLink {
  above: boolean;
  below: boolean;
}

export function buildBlockLinks(schedules: readonly BlockLesson[]): ReadonlyMap<number, BlockLink> {
  const bySeat = new Map<string, BlockLesson>();
  for (const lesson of schedules) {
    const key = blockGroupKey(lesson);
    if (key !== null && lesson.blockSeq !== null) {
      bySeat.set(`${key}:${lesson.blockSeq}`, lesson);
    }
  }
  const joined = (lesson: BlockLesson, seqStep: number): boolean => {
    const key = blockGroupKey(lesson);
    if (key === null || lesson.blockSeq === null) {
      return false;
    }
    const neighbour = bySeat.get(`${key}:${lesson.blockSeq + seqStep}`);
    return (
      neighbour !== undefined &&
      neighbour.weekday === lesson.weekday &&
      neighbour.period === lesson.period + seqStep
    );
  };
  const links = new Map<number, BlockLink>();
  for (const lesson of schedules) {
    if (blockGroupKey(lesson) !== null) {
      links.set(lesson.scheduleId, { above: joined(lesson, -1), below: joined(lesson, 1) });
    }
  }
  return links;
}
