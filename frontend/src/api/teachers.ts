import { apiClient } from "./client";
import type { Teacher, TeacherUpdate } from "../types/teacher";

// Mirrors backend/app/routers/teacher.py. Task 98: read and rename only --
// a teacher is created / 停用 with its 一般老師 account (api/users.ts).

export async function list(skip = 0, limit = 100): Promise<Teacher[]> {
  const response = await apiClient.get<Teacher[]>("/api/v1/teachers/", {
    params: { skip, limit },
  });
  return response.data;
}

export async function get(teacherId: number): Promise<Teacher> {
  const response = await apiClient.get<Teacher>(`/api/v1/teachers/${teacherId}`);
  return response.data;
}

export async function update(teacherId: number, data: TeacherUpdate): Promise<Teacher> {
  const response = await apiClient.patch<Teacher>(`/api/v1/teachers/${teacherId}`, data);
  return response.data;
}
