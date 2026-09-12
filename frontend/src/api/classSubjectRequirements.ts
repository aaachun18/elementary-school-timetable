import { apiClient } from "./client";
import type {
  ClassSubjectRequirement,
  ClassSubjectRequirementCreate,
  ClassSubjectRequirementUpdate,
} from "../types/classSubjectRequirement";

// Mirrors backend/app/routers/class_subject_requirement.py's 5 endpoints --
// see teachers.ts for why create()/update()/remove() exist even though
// Task 31 only calls list().

export async function list(
  skip = 0,
  limit = 100,
): Promise<ClassSubjectRequirement[]> {
  const response = await apiClient.get<ClassSubjectRequirement[]>(
    "/api/v1/class-subject-requirements/",
    { params: { skip, limit } },
  );
  return response.data;
}

export async function get(requirementId: number): Promise<ClassSubjectRequirement> {
  const response = await apiClient.get<ClassSubjectRequirement>(
    `/api/v1/class-subject-requirements/${requirementId}`,
  );
  return response.data;
}

export async function create(
  data: ClassSubjectRequirementCreate,
): Promise<ClassSubjectRequirement> {
  const response = await apiClient.post<ClassSubjectRequirement>(
    "/api/v1/class-subject-requirements/",
    data,
  );
  return response.data;
}

export async function update(
  requirementId: number,
  data: ClassSubjectRequirementUpdate,
): Promise<ClassSubjectRequirement> {
  const response = await apiClient.patch<ClassSubjectRequirement>(
    `/api/v1/class-subject-requirements/${requirementId}`,
    data,
  );
  return response.data;
}

export async function remove(requirementId: number): Promise<void> {
  await apiClient.delete(`/api/v1/class-subject-requirements/${requirementId}`);
}
