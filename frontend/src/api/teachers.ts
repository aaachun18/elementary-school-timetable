import { apiClient } from "./client";
import type { Teacher, TeacherCreate, TeacherUpdate } from "../types/teacher";

// All five functions mirror the five endpoints backend/app/routers/teacher.py
// already exposes. Phase A (see docs/FRONTEND_REQUIREMENTS.md) only calls
// list()/get() -- create()/update()/remove() are written now, with full
// signatures and types, so Phase B's CRUD forms can start calling them
// directly instead of the API layer's shape having to change first.

export async function list(skip = 0, limit = 100): Promise<Teacher[]> {
  const response = await apiClient.get<Teacher[]>("/api/v1/teachers/", {
    params: { skip, limit },
  });
  return response.data;
}

export async function get(teacherId: number): Promise<Teacher> {
  const response = await apiClient.get<Teacher>(
    `/api/v1/teachers/${teacherId}`,
  );
  return response.data;
}

export async function create(data: TeacherCreate): Promise<Teacher> {
  const response = await apiClient.post<Teacher>("/api/v1/teachers/", data);
  return response.data;
}

export async function update(
  teacherId: number,
  data: TeacherUpdate,
): Promise<Teacher> {
  const response = await apiClient.patch<Teacher>(
    `/api/v1/teachers/${teacherId}`,
    data,
  );
  return response.data;
}

export async function remove(teacherId: number): Promise<void> {
  await apiClient.delete(`/api/v1/teachers/${teacherId}`);
}
