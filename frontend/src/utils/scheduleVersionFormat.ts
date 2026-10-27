import type { ScheduleVersion, ScheduleVersionStatus } from "../types/scheduleVersion";
import type { Semester } from "../types/semester";
import type { BadgeTone } from "./badgeTone";

// The one place a 排課紀錄's status becomes Chinese text and a badge, and
// a record becomes a one-line label (semester_id -> Semester ->
// academic_year_id -> year). Pure, no React.

type RecordStatusSource = Pick<ScheduleVersion, "status" | "is_published" | "copied_from_display_number">;

// Keyed by plain string so an unexpected value from the backend still
// reaches the raw-string fallback.
const STATUS_LABELS: Record<string, string> = {
  NOT_SCHEDULED: "尚未排課",
  AUTO: "自動排課",
  MANUAL: "手動排課",
  EDITING: "編輯中",
};

// Task 98: 自動排課 = info (blue), 手動排課 = manual (violet), 尚未排課 =
// warning (amber); a copy, 編輯中 or anything unknown is neutral.
const STATUS_TONES: Record<string, BadgeTone> = {
  NOT_SCHEDULED: "warning",
  AUTO: "info",
  MANUAL: "manual",
  COPIED: "neutral",
  EDITING: "neutral",
};

const PUBLISHED_LABEL = "已發布";

function known(table: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(table, key);
}

// The status alone, ignoring publication: 「自動排課」、「複製自編號 3」…
// An unknown status is shown as its raw string -- never silently presented
// as one of the known ones.
export function formatStatusOnly(record: Pick<RecordStatusSource, "status" | "copied_from_display_number">): string {
  if (record.status === "COPIED") {
    return record.copied_from_display_number === null ? "複製" : `複製自編號 ${record.copied_from_display_number}`;
  }
  return known(STATUS_LABELS, record.status) ? STATUS_LABELS[record.status] : record.status;
}

// What 排課紀錄 shows: 「已發布」 for the published record, its status
// otherwise.
export function formatRecordStatus(record: RecordStatusSource): string {
  return record.is_published ? PUBLISHED_LABEL : formatStatusOnly(record);
}

// The StatusBadge tone next to formatRecordStatus()'s text: 已發布 is
// success (green) whatever the status.
export function recordStatusTone(record: Pick<RecordStatusSource, "status" | "is_published">): BadgeTone {
  if (record.is_published) {
    return "success";
  }
  return known(STATUS_TONES, record.status) ? STATUS_TONES[record.status] : "neutral";
}

// Records with a timetable: 檢視課表, 發布, 複製此課表, 手動編輯.
const TIMETABLE_STATUSES: readonly ScheduleVersionStatus[] = ["AUTO", "MANUAL", "COPIED"];

export function hasTimetable(status: string): boolean {
  return (TIMETABLE_STATUSES as readonly string[]).includes(status);
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

export function semesterLabelOf(
  record: Pick<ScheduleVersion, "semester_id">,
  semesterById: Map<number, Semester>,
  academicYearById: Map<number, number>,
): string {
  const semester = semesterById.get(record.semester_id);
  return semester ? formatSemesterLabel(semester, academicYearById) : `學期 ID ${record.semester_id}`;
}

// 「編號 {n}・{學期}（{狀態}）」
export function formatVersionLabel(
  version: ScheduleVersion,
  semesterById: Map<number, Semester>,
  academicYearById: Map<number, number>,
): string {
  const number = version.display_number === null ? "編輯中" : `編號 ${version.display_number}`;
  return `${number}・${semesterLabelOf(version, semesterById, academicYearById)}（${formatRecordStatus(version)}）`;
}
