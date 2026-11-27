// Mirrors backend/app/schemas/teacher.py. Task 98: a teacher is created
// (and 停用 / 啟用) with its 一般老師 account; its weekly periods range and
// unavailable slots are per semester (types/semesterSettings.ts), and there
// are no teaching qualifications any more.

export interface Teacher {
  id: number;
  name: string;
  is_active: boolean;
  // The teacher's 一般老師 account, if it has one.
  user_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface TeacherUpdate {
  name?: string;
}
