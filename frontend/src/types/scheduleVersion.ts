// Mirrors backend/app/schemas/schedule_version.py in full.

// v3: what a 排課紀錄 is (backend app/models/schedule_version.py):
// - NOT_SCHEDULED 尚未排課: settings only, the only status whose settings
//   change and that 自動排課 runs on;
// - AUTO 自動排課 / MANUAL 手動排課 / COPIED 複製自編號 x: has a timetable;
// - EDITING: a manual edit's hidden working copy (never listed).
// Publishing is a separate flag (is_published), one per semester.
export type ScheduleVersionStatus = "NOT_SCHEDULED" | "AUTO" | "MANUAL" | "COPIED" | "EDITING";

export interface ScheduleVersion {
  id: number;
  semester_id: number;
  // 編號 -- one sequence per school, oldest first; null only for EDITING.
  version_number: number | null;
  status: ScheduleVersionStatus;
  is_published: boolean;
  // COPIED: the 編號 it was copied from.
  copied_from_number: number | null;
  // EDITING: the record it edits.
  editing_source_id: number | null;
  // 備註.
  note: string | null;
  created_at: string;
  updated_at: string;
}

// A new record is always 尚未排課, numbered by the backend.
export interface ScheduleVersionCreate {
  semester_id: number;
}

// PATCH changes only the 備註 (an empty one is cleared).
export interface ScheduleVersionUpdate {
  note: string | null;
}

// Body for POST /schedule-versions/{id}/copy (複製此課表): any semester of
// the source's academic year; null = the source's own semester.
export interface ScheduleVersionCopy {
  target_semester_id: number | null;
}
