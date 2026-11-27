// 停用 subjects: their 年級科目需求 are hidden (kept -- old records came
// from them, and 啟用 brings them back), and the wizard's 科目需求 step
// says when some were left out of this scheduling. Pure, no React
// (subjectDeactivation.test.ts).

// 學校資料 > 科目需求: the requirements of 啟用 subjects, and those of 停用
// ones (shown only after 「顯示」).
export function splitBySubjectActive<T extends { subject_id: number }>(
  requirements: readonly T[],
  activeSubjectIds: ReadonlySet<number>,
): { shown: T[]; hidden: T[] } {
  return {
    shown: requirements.filter((item) => activeSubjectIds.has(item.subject_id)),
    hidden: requirements.filter((item) => !activeSubjectIds.has(item.subject_id)),
  };
}

// The line under the table; null when nothing is hidden.
export function hiddenRequirementsNote(hiddenCount: number): string | null {
  return hiddenCount === 0 ? null : `另有 ${hiddenCount} 筆已停用科目的需求已隱藏`;
}

// 精靈 科目需求: null when no 停用 subject was left out.
export function skippedSubjectsNote(skippedCount: number): string | null {
  return skippedCount === 0 ? null : `有 ${skippedCount} 個已停用科目的需求未納入本次排課`;
}
