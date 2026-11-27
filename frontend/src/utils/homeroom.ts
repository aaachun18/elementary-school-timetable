// 導師 in the wizard's 教師設定 step: every class needs one before 下一步,
// a teacher is 導師 of at most one class. Pure functions, no React.

// Classes in grade order (then the order they were made), for the 導師
// dropdowns and messages.
export function sortClassesByGrade<T extends { id: number; grade_id: number }>(
  classes: readonly T[],
  gradeLevelById: ReadonlyMap<number, number>,
): T[] {
  return [...classes].sort(
    (a, b) => (gradeLevelById.get(a.grade_id) ?? 0) - (gradeLevelById.get(b.grade_id) ?? 0) || a.id - b.id,
  );
}

// The classes still without a 導師 -- what one teacher's dropdown offers
// besides the class they already have.
export function classesWithoutHomeroom<T extends { id: number }>(
  classes: readonly T[],
  assignedClassIds: ReadonlySet<number>,
): T[] {
  return classes.filter((item) => !assignedClassIds.has(item.id));
}

// 「一年甲班、一年乙班未被指派導師，修正後方可進入下一步」, or null when every
// class has one.
export function missingHomeroomMessage(
  classes: readonly { id: number; name: string }[],
  assignedClassIds: ReadonlySet<number>,
): string | null {
  const missing = classesWithoutHomeroom(classes, assignedClassIds);
  if (missing.length === 0) {
    return null;
  }
  return `${missing.map((item) => item.name).join("、")}未被指派導師，修正後方可進入下一步。`;
}
