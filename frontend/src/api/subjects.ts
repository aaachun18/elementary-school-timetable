import { apiClient } from "./client";
import type { Subject, SubjectCreate, SubjectUpdate } from "../types/subject";

// Mirrors backend/app/routers/subject.py's 5 endpoints -- see teachers.ts
// for why create()/update()/remove() exist even though Phase A only calls
// list()/get().

export async function list(skip = 0, limit = 100): Promise<Subject[]> {
  const response = await apiClient.get<Subject[]>("/api/v1/subjects/", {
    params: { skip, limit },
  });
  return response.data;
}

export async function get(subjectId: number): Promise<Subject> {
  const response = await apiClient.get<Subject>(`/api/v1/subjects/${subjectId}`);
  return response.data;
}

export async function create(data: SubjectCreate): Promise<Subject> {
  const response = await apiClient.post<Subject>("/api/v1/subjects/", data);
  return response.data;
}

export async function update(
  subjectId: number,
  data: SubjectUpdate,
): Promise<Subject> {
  const response = await apiClient.patch<Subject>(
    `/api/v1/subjects/${subjectId}`,
    data,
  );
  return response.data;
}

export async function remove(subjectId: number): Promise<void> {
  await apiClient.delete(`/api/v1/subjects/${subjectId}`);
}
