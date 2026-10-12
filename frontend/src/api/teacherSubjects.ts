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

// POST /api/v1/teachers/{id}/subjects -- Task 46. Duplicate (uq_teacher_subject)
// surfaces as the usual 409 DuplicateValueError; an invalid subjectId
// surfaces as the usual 422 InvalidReferenceError. Neither needs special
// handling here -- both already have a generic Chinese message.
export async function create(teacherId: number, subjectId: number): Promise<Subject> {
  const response = await apiClient.post<Subject>(
    `/api/v1/teachers/${teacherId}/subjects`,
    { subject_id: subjectId },
  );
  return response.data;
}

export async function remove(teacherId: number, subjectId: number): Promise<void> {
  await apiClient.delete(`/api/v1/teachers/${teacherId}/subjects/${subjectId}`);
}
