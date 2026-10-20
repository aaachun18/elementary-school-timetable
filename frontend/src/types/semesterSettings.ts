// Task 98: mirrors backend/app/schemas/semester_settings.py -- one
// semester's scheduling settings (the wizard's steps 4-6 and 8).

export interface SemesterTeacherEntry {
  teacher_id: number;
  min_weekly_periods: number;
  max_weekly_periods: number;
  unavailable_time_slot_ids: number[];
}

export interface SemesterTeacher extends SemesterTeacherEntry {
  teacher_name: string;
}

export interface GradeTimeSlots {
  grade_id: number;
  time_slot_ids: number[];
}
