import { apiClient } from "./client";
import type { PasswordReset, User, UserCreate } from "../types/user";

// Task 59: the account-management calls. All ADMIN-only on the backend
// (backend/app/routers/users.py); apiClient attaches the stored JWT to
// every request automatically.

export async function list(): Promise<User[]> {
  const response = await apiClient.get<User[]>("/api/v1/users/");
  return response.data;
}

// Creating an account deliberately reuses POST /api/v1/auth/register
// (Task 57) rather than a separate users endpoint. Its response carries a
// few more fields than a list row (is_active/created_at/updated_at), so
// only the fields this page's User type actually describes are kept.
export async function create(data: UserCreate): Promise<User> {
  const response = await apiClient.post<User>("/api/v1/auth/register", data);
  const { id, username, role } = response.data;
  return { id, username, role };
}

export async function resetPassword(userId: number, data: PasswordReset): Promise<void> {
  await apiClient.patch(`/api/v1/users/${userId}/password`, data);
}

export async function remove(userId: number): Promise<void> {
  await apiClient.delete(`/api/v1/users/${userId}`);
}
