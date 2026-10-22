// 學校資料 > 科目需求: the subject of a new requirement is typed freely. A
// name the school already has (spaces around it ignored) means that
// subject; any other name is a new subject, created on save.

export function normalizeSubjectName(name: string): string {
  return name.trim();
}

export function findSubjectByName<T extends { name: string }>(
  subjects: readonly T[],
  name: string,
): T | undefined {
  const wanted = normalizeSubjectName(name);
  return subjects.find((subject) => normalizeSubjectName(subject.name) === wanted);
}
