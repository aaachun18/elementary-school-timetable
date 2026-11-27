import { apiClient } from "./client";
import type { Grade } from "../types/grade";

// Mirrors backend/app/routers/grade.py. Read only: a school's grades are
// built with the school from its type.

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
