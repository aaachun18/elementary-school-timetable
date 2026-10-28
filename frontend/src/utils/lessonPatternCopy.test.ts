import { describe, expect, it } from "vitest";
import {
  copyPatternsDisabledReason,
  copyPatternsResultText,
  isPatternCompatible,
  planLessonPatternCopy,
  type PatternCopyRequirement,
} from "./lessonPatternCopy";

function requirement(
  id: number,
  classId: number,
  subjectId: number,
  weeklyPeriods: number,
  pattern: string | null = null,
  isLocked = false,
): PatternCopyRequirement {
  return {
    id,
    class_id: classId,
    subject_id: subjectId,
    weekly_periods: weeklyPeriods,
    lesson_pattern: pattern,
    is_locked: isLocked,
  };
}

describe("isPatternCompatible", () => {
  it("needs the blocks to add up to the weekly periods", () => {
    expect(isPatternCompatible("2+1", 3)).toBe(true);
    expect(isPatternCompatible("2+1", 4)).toBe(false);
    expect(isPatternCompatible("2+2", 3)).toBe(false);
  });

  it("always fits 「不指定連堂」", () => {
    expect(isPatternCompatible(null, 5)).toBe(true);
    expect(isPatternCompatible(undefined, 1)).toBe(true);
    expect(isPatternCompatible("", 2)).toBe(true);
  });
});

describe("planLessonPatternCopy", () => {
  // Classes 1 (source), 2 and 3 of one grade; subjects 10 (3 periods) and 20.
  const base = [
    requirement(1, 1, 10, 3, "2+1"),
    requirement(2, 1, 20, 2, null),
    requirement(3, 2, 10, 3, null),
    requirement(4, 2, 20, 2, "2"),
    requirement(5, 3, 10, 4, null),
  ];

  it("copies each subject's pattern to the same subject of the other classes", () => {
    const plan = planLessonPatternCopy({
      sourceClassId: 1,
      gradeClassIds: [1, 2, 3],
      requirements: base,
      combinedRequirementIds: new Set(),
    });
    expect(plan.items).toEqual([
      { id: 3, lesson_pattern: "2+1" },
      { id: 4, lesson_pattern: null },
    ]);
    expect(plan.copiedClassIds).toEqual([2]);
    // Class 3: subject 10 has 4 periods (2+1 doesn't fit), no subject 20.
    expect(plan.skippedCount).toBe(2);
  });

  it("never touches the source class or another grade", () => {
    const plan = planLessonPatternCopy({
      sourceClassId: 1,
      gradeClassIds: [1, 2],
      requirements: [...base, requirement(6, 9, 10, 3, null)],
      combinedRequirementIds: new Set(),
    });
    expect(plan.items.map((item) => item.id)).toEqual([3, 4]);
    expect(plan.skippedCount).toBe(0);
  });

  it("skips a locked requirement and one in a 共同排課", () => {
    const locked = planLessonPatternCopy({
      sourceClassId: 1,
      gradeClassIds: [1, 2],
      requirements: [requirement(1, 1, 10, 3, "2+1"), requirement(3, 2, 10, 3, null, true)],
      combinedRequirementIds: new Set(),
    });
    expect(locked.items).toEqual([]);
    expect(locked.skippedCount).toBe(1);

    const combined = planLessonPatternCopy({
      sourceClassId: 1,
      gradeClassIds: [1, 2],
      requirements: base,
      combinedRequirementIds: new Set([3]),
    });
    expect(combined.items).toEqual([{ id: 4, lesson_pattern: null }]);
    expect(combined.skippedCount).toBe(1);
  });

  it("has nothing to do for a grade of one class", () => {
    const plan = planLessonPatternCopy({
      sourceClassId: 1,
      gradeClassIds: [1],
      requirements: base,
      combinedRequirementIds: new Set(),
    });
    expect(plan).toEqual({ items: [], copiedClassIds: [], skippedCount: 0 });
  });
});

describe("copyPatternsDisabledReason", () => {
  it("explains why the button can't be used", () => {
    expect(copyPatternsDisabledReason(1, 3)).toBe("同年級只有這一個班級，沒有可以複製的班級");
    expect(copyPatternsDisabledReason(3, 0)).toBe("這個班級還沒有科目需求");
    expect(copyPatternsDisabledReason(3, 2)).toBeNull();
  });
});

describe("copyPatternsResultText", () => {
  it("says how many classes got it, and how many items were skipped", () => {
    expect(copyPatternsResultText(2, 0)).toBe("已複製到 2 個班級");
    expect(copyPatternsResultText(1, 3)).toBe("已複製到 1 個班級，略過 3 項（節數不符或無此科目）");
  });
});
