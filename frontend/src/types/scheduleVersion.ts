// Mirrors backend/app/schemas/schedule_version.py in full.

export interface ScheduleVersion {
  id: number;
  semester_id: number;
  version_number: number;
  status: "DRAFT" | "PUBLISHED";
  created_at: string;
  updated_at: string;
}

export interface ScheduleVersionCreate {
  semester_id: number;
  version_number: number;
  status: "DRAFT" | "PUBLISHED";
}

export interface ScheduleVersionUpdate {
  semester_id?: number;
  version_number?: number;
  status?: "DRAFT" | "PUBLISHED";
}
