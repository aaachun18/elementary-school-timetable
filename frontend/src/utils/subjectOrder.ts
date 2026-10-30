// The one order subjects are listed in everywhere (學校資料的科目、年級科目
// 需求、精靈與排課設定的科目需求): 國語、英語、數學、生活、美勞、自然、社會、
// 藝術、音樂、健康、體育、綜合. Schools name subjects a little differently
// (國語文 / 國語 / 國文), so a subject takes the place of the first word
// below its name contains; one containing none of them comes after all of
// those. Ties (same place) go by name. Pure, no React.

const ORDER_KEYWORDS: readonly (readonly string[])[] = [
  ["國語", "國文"],
  ["英"],
  ["數"],
  ["生活"],
  ["美勞"],
  ["自然"],
  ["社會"],
  ["藝術"],
  ["音樂"],
  ["健康"],
  ["體育"],
  ["綜合"],
];

// 0 = 國語 … 11 = 綜合; ORDER_KEYWORDS.length for any other subject.
export function subjectRank(name: string): number {
  const index = ORDER_KEYWORDS.findIndex((keywords) => keywords.some((keyword) => name.includes(keyword)));
  return index === -1 ? ORDER_KEYWORDS.length : index;
}

export function compareSubjectNames(a: string, b: string): number {
  return subjectRank(a) - subjectRank(b) || a.localeCompare(b, "zh-Hant");
}

// Anything with a subject, sorted by its subject's name (`nameOf`); a copy.
export function sortBySubject<T>(items: readonly T[], nameOf: (item: T) => string): T[] {
  return [...items].sort((a, b) => compareSubjectNames(nameOf(a), nameOf(b)));
}
