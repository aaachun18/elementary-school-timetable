// Task 80 / v3: which 排課紀錄 can be deleted. Mirrors the backend rule
// (services/schedule_version.py's delete_schedule_version()): every record
// but the semester's published one. The backend still decides; this only
// drives what the page offers.

import type { ScheduleVersion } from "../types/scheduleVersion";

// Why the published record's trash button is disabled (Task 98 Phase B).
export const PUBLISHED_DELETE_HINT = "已發布的紀錄不可刪除";

export function canDeleteRecord(record: Pick<ScheduleVersion, "is_published">): boolean {
  return !record.is_published;
}

// What the delete dialog warns about: the record goes with its settings
// and timetable.
export const DELETE_WARNING = "這筆紀錄的排課設定與課表都會一併刪除，刪除後無法復原。";
