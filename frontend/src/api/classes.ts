import { apiClient } from "./client";
import type { Class, ClassBatchCreate, ClassCreate } from "../types/class";

// Mirrors backend/app/routers/class_.py. No update: a class is only
// created and deleted.

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

// All of them or none (one transaction on the backend).
export async function createBatch(data: ClassBatchCreate): Promise<Class[]> {
  const response = await apiClient.post<Class[]>("/api/v1/classes/batch", data);
  return response.data;
}

export async function remove(classId: number): Promise<void> {
  await apiClient.delete(`/api/v1/classes/${classId}`);
}
