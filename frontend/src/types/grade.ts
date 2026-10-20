// Mirrors backend/app/schemas/grade.py. Read only: a school's grades are
// built with the school from its type (國小 1-6, 國中 7-9, 高中 10-12).

export interface Grade {
  id: number;
  name: string;
  level: number;
  created_at: string;
  updated_at: string;
}
