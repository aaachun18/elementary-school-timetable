import { apiClient } from "./client";
import type { School, SchoolCreate, SchoolUpdate } from "../types/school";

// Mirrors backend/app/routers/school.py's 5 endpoints -- see teachers.ts
// for why create()/update()/remove() exist even though Phase A only
// called list()/get(). Phase B (Task 42) is the first page to actually
// call create()/update()/remove() here.

export async function list(skip = 0, limit = 100): Promise<School[]> {
  const response = await apiClient.get<School[]>("/api/v1/schools/", {
    params: { skip, limit },
  });
  return response.data;
}

export async function get(schoolId: number): Promise<School> {
  const response = await apiClient.get<School>(`/api/v1/schools/${schoolId}`);
  return response.data;
}

export async function create(data: SchoolCreate): Promise<School> {
  const response = await apiClient.post<School>("/api/v1/schools/", data);
  return response.data;
}

export async function update(schoolId: number, data: SchoolUpdate): Promise<School> {
  const response = await apiClient.patch<School>(`/api/v1/schools/${schoolId}`, data);
  return response.data;
}

export async function remove(schoolId: number): Promise<void> {
  await apiClient.delete(`/api/v1/schools/${schoolId}`);
}
