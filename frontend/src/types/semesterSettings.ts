// Task 98: mirrors backend/app/schemas/semester_settings.py -- one 排課紀錄's
// scheduling settings (the wizard's 教師設定 and 年級與可排節次).

export interface SemesterTeacherEntry {
  teacher_id: number;
  min_weekly_periods: number;
  max_weekly_periods: number;
  unavailable_time_slot_ids: number[];
  // The class this teacher is 導師 of in the record, if any.
  homeroom_class_id: number | null;
}

export interface SemesterTeacher extends SemesterTeacherEntry {
  teacher_name: string;
}

export interface GradeTimeSlots {
  grade_id: number;
  time_slot_ids: number[];
}
