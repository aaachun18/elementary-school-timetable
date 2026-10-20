import { apiClient } from "./client";
import type { PasswordReset, User, UserCreate, UserUpdate } from "../types/user";

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

export async function remove(userId: number): Promise<void> {
  await apiClient.delete(`/api/v1/users/${userId}`);
}
