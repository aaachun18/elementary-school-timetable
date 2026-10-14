// Mirrors backend/app/schemas/class_subject_requirement.py in full.

export interface ClassSubjectRequirement {
  id: number;
  semester_id: number;
  class_id: number;
  subject_id: number;
  weekly_periods: number;
  required_teacher_id: number | null;
  required_room_type: string | null;
  consecutive_limit: number | null;
  created_at: string;
  updated_at: string;
  // Task 73: computed by the backend on every response -- true when a
  // PUBLISHED or ARCHIVED version uses this requirement's lessons, in which
  // case PATCH/DELETE are refused (409). Response-only; never sent back.
  is_locked: boolean;
}

export interface ClassSubjectRequirementCreate {
  semester_id: number;
  class_id: number;
  subject_id: number;
  weekly_periods: number;
  required_teacher_id?: number | null;
  required_room_type?: string | null;
  consecutive_limit?: number | null;
}

export interface ClassSubjectRequirementUpdate {
  semester_id?: number;
  class_id?: number;
  subject_id?: number;
  weekly_periods?: number;
  required_teacher_id?: number | null;
  required_room_type?: string | null;
  consecutive_limit?: number | null;
}

// Task 67: optional query filters for GET /class-subject-requirements
// (Task 66).
export interface ClassSubjectRequirementListFilters {
  semester_id?: number;
}
