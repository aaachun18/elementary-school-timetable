import type { ScheduleVersion } from "../types/scheduleVersion";
import type { Semester } from "../types/semester";
import { BADGE_INFO, BADGE_NEUTRAL, BADGE_SUCCESS } from "../styles/ui";

// Shared by SchedulerConsole.tsx and TimetableView.tsx -- both need to show
// a human-readable ScheduleVersion label built from semester_id ->
// Semester -> academic_year_id -> year. Extracted here on its second use
// rather than duplicated a second time.

// Task 67: the one place a version status becomes Chinese text. Keyed by
// plain string (not ScheduleVersionStatus) so an unexpected value from the
// backend still reaches formatVersionStatus()'s fallback.
const VERSION_STATUS_LABELS: Record<string, string> = {
  DRAFT: "草稿",
  PUBLISHED: "已發布",
  ARCHIVED: "已封存",
};

const VERSION_STATUS_BADGES: Record<string, string> = {
  DRAFT: BADGE_INFO,
  PUBLISHED: BADGE_SUCCESS,
  ARCHIVED: BADGE_NEUTRAL,
};

// An unknown status is shown as its raw string -- never silently presented
// as one of the known ones.
export function formatVersionStatus(status: string): string {
  return Object.prototype.hasOwnProperty.call(VERSION_STATUS_LABELS, status)
    ? VERSION_STATUS_LABELS[status]
    : status;
}

export function versionStatusBadgeClass(status: string): string {
  return Object.prototype.hasOwnProperty.call(VERSION_STATUS_BADGES, status)
    ? VERSION_STATUS_BADGES[status]
    : BADGE_NEUTRAL;
}

export function formatSemesterLabel(
  semester: Semester,
  academicYearById: Map<number, number>,
): string {
  const year = academicYearById.get(semester.academic_year_id);
  return year !== undefined
    ? `${year} 學年度第 ${semester.number} 學期`
    : `學期 ID ${semester.id}`;
}

// "{學期} v{版本號}（{狀態}）"
export function formatVersionLabel(
  version: ScheduleVersion,
  semesterById: Map<number, Semester>,
  academicYearById: Map<number, number>,
): string {
  const semester = semesterById.get(version.semester_id);
  const semesterLabel = semester
    ? formatSemesterLabel(semester, academicYearById)
    : `學期 ID ${version.semester_id}`;
  return `${semesterLabel} v${version.version_number}（${formatVersionStatus(version.status)}）`;
}
