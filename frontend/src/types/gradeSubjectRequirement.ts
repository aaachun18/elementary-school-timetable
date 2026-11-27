// Mirrors backend/app/schemas/grade_subject_requirement.py: the school's
// 科目需求 -- every class of a grade needs weekly_periods (1-6) of a
// subject. The wizard copies these into each semester's requirements.

export interface GradeSubjectRequirement {
  id: number;
  grade_id: number;
  subject_id: number;
  weekly_periods: number;
  created_at: string;
  updated_at: string;
}

export interface GradeSubjectRequirementCreate {
  grade_id: number;
  subject_id: number;
  weekly_periods: number;
}

export interface GradeSubjectRequirementUpdate {
  weekly_periods: number;
}
