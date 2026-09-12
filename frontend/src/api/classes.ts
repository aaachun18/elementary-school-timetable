import { apiClient } from "./client";
import type { Class, ClassCreate, ClassUpdate } from "../types/class";

// Mirrors backend/app/routers/class_.py's 5 endpoints -- see teachers.ts for
// why create()/update()/remove() exist even though Phase A only calls
// list()/get().

export async function list(skip = 0, limit = 100): Promise<Class[]> {
  const response = await apiClient.get<Class[]>("/api/v1/classes/", {
    params: { skip, limit },
  });
  return response.data;
}

export async function get(classId: number): Promise<Class> {
  const response = await apiClient.get<Class>(`/api/v1/classes/${classId}`);
  return response.data;
}

export async function create(data: ClassCreate): Promise<Class> {
  const response = await apiClient.post<Class>("/api/v1/classes/", data);
  return response.data;
}

export async function update(classId: number, data: ClassUpdate): Promise<Class> {
  const response = await apiClient.patch<Class>(`/api/v1/classes/${classId}`, data);
  return response.data;
}

export async function remove(classId: number): Promise<void> {
  await apiClient.delete(`/api/v1/classes/${classId}`);
}
