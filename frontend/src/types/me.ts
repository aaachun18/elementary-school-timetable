import type { UserRole } from "../utils/auth";

// Mirrors backend/app/schemas/user.py::ProfileRead -- GET /api/v1/me
// (帳號改版 個人資料維護).
export interface Profile {
  username: string;
  role: UserRole;
  // null: the 系統管理員, or an 一般老師 after 離校 (無所屬學校).
  school_id: number | null;
  school_name: string | null;
  // 教學組長 / 一般老師 only.
  name: string | null;
}

// Mirrors backend/app/schemas/user.py::OwnPasswordChange.
export interface OwnPasswordChange {
  current_password: string;
  new_password: string;
}
