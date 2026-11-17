import type { UserRole } from "../utils/auth";

// Mirrors backend/app/schemas/user.py::UserListItem -- one row of
// GET /api/v1/users/. Never includes hashed_password. 帳號改版: username
// is the email for 教學組長 / 一般老師 accounts; school_id is null for an
// 一般老師 after 離校 (無所屬學校).
export interface User {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  school_id: number | null;
  // The account's teacher name (教學組長 / 一般老師).
  teacher_name: string | null;
  // The account's current teacher row; null while it has no school.
  teacher_id: number | null;
}

// Mirrors backend/app/schemas/user.py::UsernameAvailability.
export interface UsernameAvailability {
  available: boolean;
}

// Mirrors backend/app/schemas/user.py::AccountCreate -- the body of
// POST /api/v1/users/. 系統管理員: email + school_id (creates a 教學組長);
// 教學組長: email + teacher_name (creates an 一般老師 of their school).
export interface AccountCreate {
  email: string;
  school_id?: number;
  teacher_name?: string;
}

// Mirrors backend/app/schemas/user.py::AccountCreated. initial_password
// is only set when the mail could not be sent.
export interface AccountCreated {
  user: User;
  email_sent: boolean;
  initial_password: string | null;
}

// Mirrors backend/app/schemas/user.py::UserUpdate -- the body of
// PATCH /api/v1/users/{id}, 系統管理員 only.
export interface UserUpdate {
  is_active?: boolean;
  school_id?: number;
}

// Mirrors backend/app/schemas/user.py::PasswordReset -- the body of
// PATCH /api/v1/users/{id}/password.
export interface PasswordReset {
  password: string;
}
