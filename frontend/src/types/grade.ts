// Mirrors backend/app/schemas/grade.py in full. Unlike every other lookup
// table in this app, Grade has no is_active column at all (see
// backend/app/models/grade_class.py) -- there is genuinely no field for a
// create form to omit here.

export interface Grade {
  id: number;
  name: string;
  level: number;
  created_at: string;
  updated_at: string;
}

export interface GradeCreate {
  name: string;
  level: number;
}

export interface GradeUpdate {
  name?: string;
  level?: number;
}
