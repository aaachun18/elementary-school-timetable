import { apiClient } from "./client";
import type { DeactivationImpact } from "../utils/deactivation";
import type {
  PasswordReset,
  SameNameTeacher,
  User,
  UserCreate,
  UsernameAvailability,
  UserUpdate,
} from "../types/user";

// Task 59: the account-management calls (backend/app/routers/users.py --
// Task 98: the 系統管理員 and the 教學組長, each seeing only the accounts
// they may manage); apiClient attaches the stored JWT to every request
// automatically.

// `search`: only the accounts whose 帳號名稱, 教師姓名 or 身分證字號 contains
// it (the backend searches -- the list itself only has the number masked).
export async function list(search: string | null = null): Promise<User[]> {
  const response = await apiClient.get<User[]>("/api/v1/users/", {
    params: search === null || search.trim() === "" ? undefined : { search: search.trim() },
  });
  return response.data;
}

// Creating an account deliberately reuses POST /api/v1/auth/register
// (Task 57) rather than a separate users endpoint. Its response has no
// teacher_name, so the name the form sent is used for the new row (the
// page reloads the list afterwards for the rest of the teacher fields).
interface RegisterResponse {
  id: number;
  username: string;
  role: User["role"];
  is_active: boolean;
  school_id: number | null;
}

export async function create(data: UserCreate): Promise<User> {
  const response = await apiClient.post<RegisterResponse>("/api/v1/auth/register", data);
  const { id, username, role, is_active, school_id } = response.data;
  return {
    id,
    username,
    role,
    is_active,
    school_id,
    teacher_name: data.teacher_name ?? null,
    teacher_id: null,
    national_id_masked: null,
    national_id_missing: false,
  };
}

export async function update(userId: number, data: UserUpdate): Promise<User> {
  const response = await apiClient.patch<User>(`/api/v1/users/${userId}`, data);
  return response.data;
}

export async function resetPassword(userId: number, data: PasswordReset): Promise<void> {
  await apiClient.patch(`/api/v1/users/${userId}/password`, data);
}

// The school's teachers already named `name` (a 教學組長's own school;
// the 系統管理員 passes the school).
export async function listSameNameTeachers(
  name: string,
  schoolId: number | null,
): Promise<SameNameTeacher[]> {
  const params: { name: string; school_id?: number } = { name };
  if (schoolId !== null) {
    params.school_id = schoolId;
  }
  const response = await apiClient.get<SameNameTeacher[]>("/api/v1/users/same-name-teachers", { params });
  return response.data;
}

// 新增帳號 checks the 帳號名稱 while it is typed (unique across schools).
export async function isUsernameAvailable(username: string): Promise<boolean> {
  const response = await apiClient.get<UsernameAvailability>("/api/v1/users/username-available", {
    params: { username },
  });
  return response.data.available;
}

// null clears it (refused while the school has another teacher of the name).
export async function setTeacherNationalId(teacherId: number, nationalId: string | null): Promise<SameNameTeacher> {
  const response = await apiClient.patch<SameNameTeacher>(`/api/v1/users/teachers/${teacherId}/national-id`, {
    national_id: nationalId,
  });
  return response.data;
}

export async function remove(userId: number): Promise<void> {
  await apiClient.delete(`/api/v1/users/${userId}`);
}

// What 停用 would touch (counts for DeactivateConfirmDialog).
export async function deactivationImpact(id: number): Promise<DeactivationImpact> {
  const response = await apiClient.get<DeactivationImpact>(`/api/v1/users/${id}/deactivation-impact`);
  return response.data;
}
