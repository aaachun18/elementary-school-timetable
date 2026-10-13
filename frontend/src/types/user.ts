import type { UserRole } from "../utils/auth";

// Mirrors backend/app/schemas/user.py::UserListItem -- one row of
// GET /api/v1/users/ (Task 59). Never includes hashed_password.
export interface User {
  id: number;
  username: string;
  role: UserRole;
}

// Mirrors backend/app/schemas/user.py::UserCreate -- the body of
// POST /api/v1/auth/register.
export interface UserCreate {
  username: string;
  password: string;
  role: UserRole;
}

// Mirrors backend/app/schemas/user.py::PasswordReset -- the body of
// PATCH /api/v1/users/{id}/password.
export interface PasswordReset {
  password: string;
}
