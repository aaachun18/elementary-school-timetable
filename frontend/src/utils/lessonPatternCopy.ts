// Task 103: the wizard's 「複製此連堂設定至所有同年級班級」 (科目需求 step).
// The class on screen is the source: for each of its subjects, the other
// classes of the same grade that have that subject get its 連堂樣式. Only the
// pattern is copied -- never 每週節數, 固定時段, 指定老師 or 特殊教室. Pure, no
// React (lessonPatternCopy.test.ts); the backend checks every item again and
// saves them in one transaction.

import type { LessonPatternItem } from "../types/classSubjectRequirement";
import { CANCEL_LABEL, type ConfirmText } from "./confirmText";
import { parseLessonPattern } from "./lessonPattern";

export interface PatternCopyRequirement {
  id: number;
  class_id: number;
  subject_id: number;
  weekly_periods: number;
  lesson_pattern?: string | null;
  is_locked: boolean;
}

export interface PatternCopyPlan {
  // What to send; unchanged ones included (the backend leaves them as they are).
  items: LessonPatternItem[];
  // The classes that get at least one subject's pattern.
  copiedClassIds: number[];
  // Target subjects left alone (no such subject, periods that don't fit,
  // locked, or part of a 共同排課).
  skippedCount: number;
}

// Whether `pattern` fits a requirement of `weeklyPeriods` lessons a week:
// 「不指定連堂」 always does; a pattern's blocks must add up to it (a block
// sum over the weekly periods can't be placed, one under it would leave
// lessons out -- the backend refuses both).
export function isPatternCompatible(pattern: string | null | undefined, weeklyPeriods: number): boolean {
  if (pattern === null || pattern === undefined || pattern === "") {
    return true;
  }
  const blocks = parseLessonPattern(pattern);
  return blocks !== null && blocks.reduce((sum, size) => sum + size, 0) === weeklyPeriods;
}

export function planLessonPatternCopy({
  sourceClassId,
  gradeClassIds,
  requirements,
  combinedRequirementIds,
}: {
  sourceClassId: number;
  // Every class of the source's grade (the source included).
  gradeClassIds: readonly number[];
  requirements: readonly PatternCopyRequirement[];
  // Requirements in a 共同排課 -- their pattern can't change.
  combinedRequirementIds: ReadonlySet<number>;
}): PatternCopyPlan {
  const sources = requirements.filter((item) => item.class_id === sourceClassId);
  const targetClassIds = gradeClassIds.filter((id) => id !== sourceClassId);
  const items: LessonPatternItem[] = [];
  const copied = new Set<number>();
  let skippedCount = 0;
  for (const source of sources) {
    const pattern = source.lesson_pattern ?? null;
    for (const classId of targetClassIds) {
      const target = requirements.find((item) => item.class_id === classId && item.subject_id === source.subject_id);
      if (
        target === undefined ||
        target.is_locked ||
        combinedRequirementIds.has(target.id) ||
        !isPatternCompatible(pattern, target.weekly_periods)
      ) {
        skippedCount += 1;
        continue;
      }
      items.push({ id: target.id, lesson_pattern: pattern });
      copied.add(classId);
    }
  }
  return { items, copiedClassIds: [...copied], skippedCount };
}

// The button's title when it can't be used; null when it can.
export function copyPatternsDisabledReason(gradeClassCount: number, sourceRequirementCount: number): string | null {
  if (gradeClassCount <= 1) {
    return "同年級只有這一個班級，沒有可以複製的班級";
  }
  if (sourceRequirementCount === 0) {
    return "這個班級還沒有科目需求";
  }
  return null;
}

export const COPY_PATTERNS_LABEL = "複製此連堂設定至所有同年級班級";

export const COPY_PATTERNS_CONFIRM: ConfirmText = {
  title: "複製連堂設定？",
  message: "同年級其他班級的連堂設定會被覆蓋。",
  confirmLabel: "複製",
  cancelLabel: CANCEL_LABEL,
  tone: "primary",
};

// 「已複製到 2 個班級，略過 1 項（節數不符或無此科目）」.
export function copyPatternsResultText(copiedClassCount: number, skippedCount: number): string {
  const copied = `已複製到 ${copiedClassCount} 個班級`;
  return skippedCount > 0 ? `${copied}，略過 ${skippedCount} 項（節數不符或無此科目）` : copied;
}
