// Mirrors backend/app/schemas/academic_year.py in full.
//
// Not explicitly listed in Task 32's scope, but added alongside it: a
// Semester only carries academic_year_id, not the year itself, and the
// task's own suggested ScheduleVersion label format ("{學期年份} 學期
// {semester_number} - ...") needs the actual year. Same five-set pattern
// as every other resource module, so this is a small, low-risk addition,
// not a scope change -- see Task 32's report for the explicit disclosure.

export interface AcademicYear {
  id: number;
  year: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AcademicYearCreate {
  year: number;
}

export interface AcademicYearUpdate {
  year?: number;
  is_active?: boolean;
}
