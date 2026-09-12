import { apiClient } from "./client";
import type { Subject } from "../types/subject";

// GET /api/v1/teachers/{id}/subjects -- a semantic sub-resource endpoint
// (backend/app/routers/teacher.py), not one of the standard 5 CRUD
// endpoints, so it gets its own small module instead of a list/get/create/
// update/remove set that wouldn't map to anything real (there's no
// standalone /teacher-subjects/{id} resource).
export async function listByTeacher(teacherId: number): Promise<Subject[]> {
  const response = await apiClient.get<Subject[]>(
    `/api/v1/teachers/${teacherId}/subjects`,
  );
  return response.data;
}
