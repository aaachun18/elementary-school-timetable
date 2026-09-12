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
