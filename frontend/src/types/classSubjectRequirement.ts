// Mirrors backend/app/schemas/class_subject_requirement.py in full.

export interface ClassSubjectRequirement {
  id: number;
  // v3: the 排課紀錄 whose settings it is part of.
  schedule_version_id: number;
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
  // Task 73 / v3: computed by the backend on every response -- true once
  // the record is no longer 尚未排課, in which case PATCH/DELETE are refused
  // (409). Response-only; never sent back.
  is_locked: boolean;
}

export interface ClassSubjectRequirementCreate {
  schedule_version_id: number;
  class_id: number;
  subject_id: number;
  weekly_periods: number;
  required_teacher_id?: number | null;
  required_room_id?: number | null;
  lesson_pattern?: string | null;
}

export interface ClassSubjectRequirementUpdate {
  class_id?: number;
  subject_id?: number;
  weekly_periods?: number;
  required_teacher_id?: number | null;
  required_room_id?: number | null;
  lesson_pattern?: string | null;
}

// Optional query filters for GET /class-subject-requirements.
export interface ClassSubjectRequirementListFilters {
  schedule_version_id?: number;
}

// POST /class-subject-requirements/sync: what copying the school's 科目需求
// into the record changed.
export interface RequirementSyncResult {
  created: number;
  updated: number;
  removed: number;
  // 停用 subjects whose 年級科目需求 were left out of the record.
  skipped_subjects: { id: number; name: string }[];
}
