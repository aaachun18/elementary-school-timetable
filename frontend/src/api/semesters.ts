import { apiClient } from "./client";
import type { Semester, SemesterCreate, SemesterUpdate } from "../types/semester";

// Mirrors backend/app/routers/semester.py's 5 endpoints -- see teachers.ts
// for why create()/update()/remove() exist even though Task 32 only calls
// list().

export async function list(skip = 0, limit = 100): Promise<Semester[]> {
  const response = await apiClient.get<Semester[]>("/api/v1/semesters/", {
    params: { skip, limit },
  });
  return response.data;
}

export async function get(semesterId: number): Promise<Semester> {
  const response = await apiClient.get<Semester>(`/api/v1/semesters/${semesterId}`);
  return response.data;
}

export async function create(data: SemesterCreate): Promise<Semester> {
  const response = await apiClient.post<Semester>("/api/v1/semesters/", data);
  return response.data;
}

export async function update(
  semesterId: number,
  data: SemesterUpdate,
): Promise<Semester> {
  const response = await apiClient.patch<Semester>(
    `/api/v1/semesters/${semesterId}`,
    data,
  );
  return response.data;
}

export async function remove(semesterId: number): Promise<void> {
  await apiClient.delete(`/api/v1/semesters/${semesterId}`);
}
