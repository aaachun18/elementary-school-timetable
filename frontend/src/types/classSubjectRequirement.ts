// Mirrors backend/app/schemas/class_subject_requirement.py in full.

export interface ClassSubjectRequirement {
  id: number;
  semester_id: number;
  class_id: number;
  subject_id: number;
  weekly_periods: number;
  required_teacher_id: number | null;
  // Task 98: the one special room (null: 原班教室).
  required_room_id: number | null;
  // Task 90: deprecated by the backend (Task 87) -- no rule reads it any
  // more; kept only because the API still returns it. Never shown or sent.
  consecutive_limit: number | null;
  // Task 90 (backend Task 87): lesson pattern (連堂樣式), e.g. "2+1" --
  // stored largest block first; null = no blocks. Optional: an older
  // response without it behaves as null.
  lesson_pattern?: string | null;
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
  required_room_id?: number | null;
  lesson_pattern?: string | null;
}

export interface ClassSubjectRequirementUpdate {
  semester_id?: number;
  class_id?: number;
  subject_id?: number;
  weekly_periods?: number;
  required_teacher_id?: number | null;
  required_room_id?: number | null;
  lesson_pattern?: string | null;
}

// Task 67: optional query filters for GET /class-subject-requirements
// (Task 66).
export interface ClassSubjectRequirementListFilters {
  semester_id?: number;
}

// POST /class-subject-requirements/sync: what copying the school's 科目需求
// into the semester changed. locked_requirement_ids: requirements a
// published or archived version uses -- left as they were.
export interface RequirementSyncResult {
  created: number;
  updated: number;
  removed: number;
  locked_requirement_ids: number[];
}
