// Mirrors backend/app/schemas/schedule_version.py in full.

// Task 67: ARCHIVED (Task 64) -- a previously PUBLISHED version, kept as a
// locked historical record. A semester has at most one PUBLISHED version;
// publishing another one archives it automatically.
export type ScheduleVersionStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";

export interface ScheduleVersion {
  id: number;
  semester_id: number;
  version_number: number;
  status: ScheduleVersionStatus;
  created_at: string;
  updated_at: string;
}

// The backend only ever creates DRAFT versions (ScheduleVersionCreate's
// status is Literal["DRAFT"]) -- publishing is a separate status change.
export interface ScheduleVersionCreate {
  semester_id: number;
  version_number: number;
  status: "DRAFT";
}

export interface ScheduleVersionUpdate {
  semester_id?: number;
  version_number?: number;
  status?: ScheduleVersionStatus;
}

// Body for POST /schedule-versions/{id}/copy (Task 62). null (or the
// source's own semester) = same-semester copy; another semester of the same
// academic year = cross-semester copy.
export interface ScheduleVersionCopy {
  target_semester_id: number | null;
}
