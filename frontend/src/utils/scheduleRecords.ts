// Task 98: the order of the 排課紀錄 list -- newest academic year first,
// then the second semester before the first, then the newest version of a
// semester first. Pure, no React.

import type { ScheduleVersion } from "../types/scheduleVersion";
import type { Semester } from "../types/semester";

export function sortRecords(
  versions: readonly ScheduleVersion[],
  semesterById: ReadonlyMap<number, Semester>,
  academicYearById: ReadonlyMap<number, number>,
): ScheduleVersion[] {
  function key(version: ScheduleVersion): [number, number, number] {
    const semester = semesterById.get(version.semester_id);
    const year = semester === undefined ? 0 : (academicYearById.get(semester.academic_year_id) ?? 0);
    return [year, semester?.number ?? 0, version.version_number];
  }
  return [...versions].sort((a, b) => {
    const [yearA, numberA, versionA] = key(a);
    const [yearB, numberB, versionB] = key(b);
    return yearB - yearA || numberB - numberA || versionB - versionA || b.id - a.id;
  });
}
