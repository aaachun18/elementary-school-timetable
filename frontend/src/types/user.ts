import type { UserRole } from "../utils/auth";

// Mirrors backend/app/schemas/user.py::UserListItem -- one row of
// GET /api/v1/users/ (Task 59). Never includes hashed_password. Task 98
// added is_active, school_id (null for a 系統管理員) and teacher_name
// (an 一般老師 account's Teacher).
export interface User {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  school_id: number | null;
  teacher_name: string | null;
}

// Mirrors backend/app/schemas/user.py::UserCreate -- the body of
// POST /api/v1/auth/register. Task 98: school_id is required when the
// 系統管理員 creates a 教學組長 / 一般老師 (a 教學組長 leaves it out: their
// own school is used); teacher_name is required for an 一般老師.
export interface UserCreate {
  username: string;
  password: string;
  role: UserRole;
  school_id?: number;
  teacher_name?: string;
  // 身分證字號: only when the school already has a teacher of this name.
  teacher_national_id?: string;
}

// Mirrors backend/app/schemas/user.py::SameNameTeacher -- a teacher of the
// school with the name being entered; whether their 身分證字號 is set,
// never the number itself.
export interface SameNameTeacher {
  teacher_id: number;
  teacher_name: string;
  school_id: number;
  username: string | null;
  has_national_id: boolean;
}

// Mirrors backend/app/schemas/user.py::UserUpdate -- the body of
// PATCH /api/v1/users/{id} (Task 98). school_id: 系統管理員 only.
export interface UserUpdate {
  is_active?: boolean;
  school_id?: number;
}

// Mirrors backend/app/schemas/user.py::PasswordReset -- the body of
// PATCH /api/v1/users/{id}/password.
export interface PasswordReset {
  password: string;
}
