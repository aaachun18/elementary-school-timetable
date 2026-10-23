import { apiClient } from "./client";
import type { PasswordReset, SameNameTeacher, User, UserCreate, UserUpdate } from "../types/user";

// Task 59: the account-management calls (backend/app/routers/users.py --
// Task 98: the 系統管理員 and the 教學組長, each seeing only the accounts
// they may manage); apiClient attaches the stored JWT to every request
// automatically.

export async function list(): Promise<User[]> {
  const response = await apiClient.get<User[]>("/api/v1/users/");
  return response.data;
}

// Creating an account deliberately reuses POST /api/v1/auth/register
// (Task 57) rather than a separate users endpoint. Its response has no
// teacher_name, so the name the form sent is used for the new row.
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
  return { id, username, role, is_active, school_id, teacher_name: data.teacher_name ?? null };
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

export async function setTeacherNationalId(teacherId: number, nationalId: string): Promise<SameNameTeacher> {
  const response = await apiClient.patch<SameNameTeacher>(`/api/v1/users/teachers/${teacherId}/national-id`, {
    national_id: nationalId,
  });
  return response.data;
}

export async function remove(userId: number): Promise<void> {
  await apiClient.delete(`/api/v1/users/${userId}`);
}
