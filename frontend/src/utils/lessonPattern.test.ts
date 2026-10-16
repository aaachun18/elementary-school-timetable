import { describe, expect, it } from "vitest";
import {
  NO_PATTERN,
  countTeachingDays,
  describeLessonPattern,
  formatBlockPosition,
  formatLessonPattern,
  isLessonPatternOffered,
  lessonPatternOptions,
  parseLessonPattern,
} from "./lessonPattern";

const values = (weeklyPeriods: number | null, days: number | null = 5): string[] =>
  lessonPatternOptions(weeklyPeriods, days).map((option) => option.value);

describe("lessonPatternOptions", () => {
  it("lists every pattern of 1-3 lesson blocks, most blocks first, after 不指定", () => {
    expect(values(3)).toEqual([NO_PATTERN, "1+1+1", "2+1", "3"]);
    expect(values(2)).toEqual([NO_PATTERN, "1+1", "2"]);
    expect(values(4)).toEqual([NO_PATTERN, "1+1+1+1", "2+1+1", "2+2", "3+1"]);
  });

  it("never offers a block longer than 3 or the same pattern twice", () => {
    const five = values(5);
    expect(five).toEqual([NO_PATTERN, "1+1+1+1+1", "2+1+1+1", "2+2+1", "3+1+1", "3+2"]);
    expect(new Set(five).size).toBe(five.length);
    expect(values(6)).not.toContain("6");
  });

  it("leaves out patterns with more blocks than teaching days", () => {
    expect(values(3, 2)).toEqual([NO_PATTERN, "2+1", "3"]);
    expect(values(5, 2)).toEqual([NO_PATTERN, "3+2"]);
    // Unknown days: nothing is filtered.
    expect(values(5, null)).toContain("1+1+1+1+1");
  });

  it("offers nothing for one lesson a week or no valid number", () => {
    expect(values(1)).toEqual([]);
    expect(values(0)).toEqual([]);
    expect(values(null)).toEqual([]);
    expect(values(2.5)).toEqual([]);
  });

  it("labels each choice in plain words", () => {
    const labels = lessonPatternOptions(3, 5).map((option) => option.label);
    expect(labels).toEqual([
      "不指定連堂",
      "1+1+1（3 節分開，各排不同天）",
      "2+1（一組 2 節連堂 + 一節單獨，不同天）",
      "3（3 節連堂）",
    ]);
  });
});

describe("describeLessonPattern", () => {
  it("counts blocks of each size", () => {
    expect(describeLessonPattern("2+2+1")).toBe("兩組 2 節連堂 + 一節單獨，不同天");
    expect(describeLessonPattern("3+2")).toBe("一組 3 節連堂 + 一組 2 節連堂，不同天");
    expect(describeLessonPattern("2+1+1")).toBe("一組 2 節連堂 + 兩節單獨，不同天");
    expect(describeLessonPattern("2")).toBe("2 節連堂");
    expect(describeLessonPattern("1+1")).toBe("2 節分開，各排不同天");
  });

  it("shows something unparseable as it is", () => {
    expect(describeLessonPattern("4+1")).toBe("4+1");
  });
});

describe("parseLessonPattern", () => {
  it("reads 1-3s joined by +", () => {
    expect(parseLessonPattern("2+1")).toEqual([2, 1]);
    expect(parseLessonPattern(" 2 + 1 ")).toEqual([2, 1]);
    expect(parseLessonPattern("")).toBeNull();
    expect(parseLessonPattern("2+")).toBeNull();
    expect(parseLessonPattern("0+2")).toBeNull();
    expect(parseLessonPattern("a")).toBeNull();
  });
});

describe("isLessonPatternOffered", () => {
  it("is true for 不指定 and listed choices only", () => {
    const options = lessonPatternOptions(3, 5);
    expect(isLessonPatternOffered(NO_PATTERN, options)).toBe(true);
    expect(isLessonPatternOffered("2+1", options)).toBe(true);
    expect(isLessonPatternOffered("2+2", options)).toBe(false);
    // After weekly periods drop to 1 there are no choices at all.
    expect(isLessonPatternOffered("2+1", lessonPatternOptions(1, 5))).toBe(false);
  });
});

describe("countTeachingDays", () => {
  it("counts weekdays with a teaching period", () => {
    expect(
      countTeachingDays([
        { weekday: 1, is_teaching_period: true },
        { weekday: 1, is_teaching_period: false },
        { weekday: 2, is_teaching_period: true },
        { weekday: 6, is_teaching_period: false },
      ]),
    ).toBe(2);
    expect(countTeachingDays([])).toBeNull();
    expect(countTeachingDays(null)).toBeNull();
  });
});

describe("formatLessonPattern / formatBlockPosition", () => {
  it("formats the list cell", () => {
    expect(formatLessonPattern("2+1")).toBe("2+1（一組 2 節連堂 + 一節單獨，不同天）");
    expect(formatLessonPattern(null)).toBe("不指定");
    expect(formatLessonPattern(undefined)).toBe("不指定");
  });

  it("formats a lesson's place in its block", () => {
    expect(formatBlockPosition(1, 2, 2)).toBe("第 1 組第 2 節");
    expect(formatBlockPosition(2, 1, 1)).toBe("第 2 組");
    expect(formatBlockPosition(null, null, 0)).toBe("");
    expect(formatBlockPosition(undefined, undefined, 0)).toBe("");
  });
});
