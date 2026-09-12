// Mirrors backend/app/schemas/teacher.py -- kept in sync deliberately with
// EVERY field on TeacherRead/TeacherCreate/TeacherUpdate, not just the
// subset the read-only Phase A pages currently render (see
// docs/FRONTEND_REQUIREMENTS.md Task 27 appendix on why).

export interface Teacher {
  id: number;
  name: string;
  is_active: boolean;
  min_weekly_periods: number;
  max_weekly_periods: number;
  created_at: string;
  updated_at: string;
}

export interface TeacherCreate {
  name: string;
  min_weekly_periods: number;
  max_weekly_periods: number;
}

export interface TeacherUpdate {
  name?: string;
  is_active?: boolean;
  min_weekly_periods?: number;
  max_weekly_periods?: number;
}
