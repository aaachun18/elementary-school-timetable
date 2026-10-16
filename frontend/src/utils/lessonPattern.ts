// Task 90: the lesson pattern (連堂樣式) of a requirement -- which choices
// the requirement form offers and how a pattern reads on screen. Pure
// functions, no React. The backend (app/services/lesson_pattern.py) is the
// authority: every block 1-3 lessons, the blocks add up to weekly_periods,
// stored largest block first ("1+2" is stored as "2+1"), null = no blocks.

// Mirrors the backend's block size range.
export const MIN_BLOCK_SIZE = 1;
export const MAX_BLOCK_SIZE = 3;

// The form's 「不指定連堂」 choice -- a <select> value can't be null.
export const NO_PATTERN = "";

export interface LessonPatternOption {
  // NO_PATTERN or a pattern such as "2+1".
  value: string;
  label: string;
}

const NO_PATTERN_LABEL = "不指定連堂";

// Every way of writing `total` as blocks of 1-3 lessons, each written
// largest block first, so every pattern appears exactly once. Ordered
// largest first block first ("3", "2+1", "1+1+1").
function partitions(total: number, largest: number): number[][] {
  if (total === 0) {
    return [[]];
  }
  const result: number[][] = [];
  for (let size = Math.min(largest, total); size >= MIN_BLOCK_SIZE; size -= 1) {
    for (const rest of partitions(total - size, size)) {
      result.push([size, ...rest]);
    }
  }
  return result;
}

const COUNT_WORDS = ["", "一", "兩", "三", "四", "五", "六", "七", "八", "九", "十"];

function countWord(count: number): string {
  return COUNT_WORDS[count] ?? String(count);
}

// "2+1" -> "一組 2 節連堂 + 一節單獨，不同天"; all single lessons ->
// "3 節分開，各排不同天"; one block -> "3 節連堂".
export function describeLessonPattern(pattern: string): string {
  const blocks = parseLessonPattern(pattern);
  if (blocks === null || blocks.length === 0) {
    return pattern;
  }
  const total = blocks.reduce((sum, size) => sum + size, 0);
  if (blocks.every((size) => size === 1)) {
    return blocks.length === 1 ? "1 節" : `${total} 節分開，各排不同天`;
  }
  if (blocks.length === 1) {
    return `${blocks[0]} 節連堂`;
  }
  const parts: string[] = [];
  for (let size = MAX_BLOCK_SIZE; size >= MIN_BLOCK_SIZE; size -= 1) {
    const count = blocks.filter((block) => block === size).length;
    if (count === 0) {
      continue;
    }
    parts.push(size === 1 ? `${countWord(count)}節單獨` : `${countWord(count)}組 ${size} 節連堂`);
  }
  return `${parts.join(" + ")}，不同天`;
}

// "2+1" -> [2, 1]; null for anything that isn't 1-3s joined by "+".
export function parseLessonPattern(pattern: string): number[] | null {
  const text = pattern.replace(/\s+/g, "");
  if (text === "") {
    return null;
  }
  const blocks = text.split("+").map((part) => (/^\d+$/.test(part) ? Number(part) : NaN));
  if (blocks.some((size) => !(size >= MIN_BLOCK_SIZE && size <= MAX_BLOCK_SIZE))) {
    return null;
  }
  return blocks;
}

// How many days of the week have a teaching period -- a pattern may have
// at most that many blocks (they go on different days). null when the
// time slots aren't known (then nothing is filtered).
export function countTeachingDays(
  timeSlots: readonly { weekday: number; is_teaching_period: boolean }[] | null,
): number | null {
  if (timeSlots === null) {
    return null;
  }
  const days = new Set(
    timeSlots.filter((slot) => slot.is_teaching_period).map((slot) => slot.weekday),
  );
  return days.size === 0 ? null : days.size;
}

// The form's choices for a requirement of `weeklyPeriods` lessons a week:
// 「不指定連堂」 plus every pattern with at most `teachingDays` blocks, most
// blocks first. Empty -- the form hides the choice -- when there is
// nothing to choose: one lesson a week, or no valid weekly periods yet.
export function lessonPatternOptions(
  weeklyPeriods: number | null,
  teachingDays: number | null,
): LessonPatternOption[] {
  if (weeklyPeriods === null || !Number.isInteger(weeklyPeriods) || weeklyPeriods < 2) {
    return [];
  }
  const patterns = partitions(weeklyPeriods, MAX_BLOCK_SIZE)
    .filter((blocks) => teachingDays === null || blocks.length <= teachingDays)
    .reverse();
  return [
    { value: NO_PATTERN, label: NO_PATTERN_LABEL },
    ...patterns.map((blocks) => {
      const value = blocks.join("+");
      return { value, label: `${value}（${describeLessonPattern(value)}）` };
    }),
  ];
}

// Whether `pattern` (NO_PATTERN included) is one of the choices.
export function isLessonPatternOffered(
  pattern: string,
  options: readonly LessonPatternOption[],
): boolean {
  return pattern === NO_PATTERN || options.some((option) => option.value === pattern);
}

// The requirement list's cell: "2+1（…）" or 「不指定」.
export function formatLessonPattern(pattern: string | null | undefined): string {
  if (pattern === null || pattern === undefined || pattern === "") {
    return "不指定";
  }
  return `${pattern}（${describeLessonPattern(pattern)}）`;
}

// A lesson's place in its block, short: 「第 1 組第 2 節」, or just
// 「第 2 組」 for a block of one lesson. "" for a lesson in no block.
export function formatBlockPosition(
  blockNo: number | null | undefined,
  blockSeq: number | null | undefined,
  blockSize: number,
): string {
  if (blockNo === null || blockNo === undefined) {
    return "";
  }
  if (blockSize <= 1 || blockSeq === null || blockSeq === undefined) {
    return `第 ${blockNo} 組`;
  }
  return `第 ${blockNo} 組第 ${blockSeq} 節`;
}
