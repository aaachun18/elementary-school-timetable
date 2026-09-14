// Mirrors backend/app/schemas/semester.py in full.

export interface Semester {
  id: number;
  academic_year_id: number;
  number: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SemesterCreate {
  academic_year_id: number;
  number: number;
}

export interface SemesterUpdate {
  academic_year_id?: number;
  number?: number;
  is_active?: boolean;
}
