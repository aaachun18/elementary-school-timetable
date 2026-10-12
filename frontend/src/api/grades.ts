import { apiClient } from "./client";
import type { Grade, GradeCreate, GradeUpdate } from "../types/grade";

// Mirrors backend/app/routers/grade.py's 5 endpoints -- see teachers.ts
// for why create()/update()/remove() exist even though this batch (Task
// 44) only ever calls list(), to populate Class's grade_id dropdown.
// Grade itself isn't one of this batch's three CRUD tables.

export async function list(skip = 0, limit = 100): Promise<Grade[]> {
  const response = await apiClient.get<Grade[]>("/api/v1/grades/", {
    params: { skip, limit },
  });
  return response.data;
}

export async function get(gradeId: number): Promise<Grade> {
  const response = await apiClient.get<Grade>(`/api/v1/grades/${gradeId}`);
  return response.data;
}

export async function create(data: GradeCreate): Promise<Grade> {
  const response = await apiClient.post<Grade>("/api/v1/grades/", data);
  return response.data;
}

export async function update(gradeId: number, data: GradeUpdate): Promise<Grade> {
  const response = await apiClient.patch<Grade>(`/api/v1/grades/${gradeId}`, data);
  return response.data;
}

export async function remove(gradeId: number): Promise<void> {
  await apiClient.delete(`/api/v1/grades/${gradeId}`);
}
