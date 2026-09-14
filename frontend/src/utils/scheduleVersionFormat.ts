import type { ScheduleVersion } from "../types/scheduleVersion";
import type { Semester } from "../types/semester";

// Shared by SchedulerConsole.tsx and TimetableView.tsx -- both need to show
// a human-readable ScheduleVersion label built from semester_id ->
// Semester -> academic_year_id -> year. Extracted here on its second use
// rather than duplicated a second time.

export function formatSemesterLabel(
  semester: Semester,
  academicYearById: Map<number, number>,
): string {
  const year = academicYearById.get(semester.academic_year_id);
  return year !== undefined
    ? `${year} 學年度第 ${semester.number} 學期`
    : `學期 ID ${semester.id}`;
}

export function formatVersionLabel(
  version: ScheduleVersion,
  semesterById: Map<number, Semester>,
  academicYearById: Map<number, number>,
): string {
  const semester = semesterById.get(version.semester_id);
  const semesterLabel = semester
    ? formatSemesterLabel(semester, academicYearById)
    : `學期 ID ${version.semester_id}`;
  const statusLabel = version.status === "DRAFT" ? "草稿" : "已發布";
  return `${semesterLabel} - ${statusLabel} v${version.version_number}`;
}
