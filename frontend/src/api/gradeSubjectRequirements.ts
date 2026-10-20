import { apiClient } from "./client";
import type {
  GradeSubjectRequirement,
  GradeSubjectRequirementCreate,
  GradeSubjectRequirementUpdate,
} from "../types/gradeSubjectRequirement";

// Mirrors backend/app/routers/grade_subject_requirement.py (學校資料 >
// 科目需求).

export async function list(): Promise<GradeSubjectRequirement[]> {
  const response = await apiClient.get<GradeSubjectRequirement[]>(
    "/api/v1/grade-subject-requirements/",
  );
  return response.data;
}

export async function create(
  data: GradeSubjectRequirementCreate,
): Promise<GradeSubjectRequirement> {
  const response = await apiClient.post<GradeSubjectRequirement>(
    "/api/v1/grade-subject-requirements/",
    data,
  );
  return response.data;
}

export async function update(
  requirementId: number,
  data: GradeSubjectRequirementUpdate,
): Promise<GradeSubjectRequirement> {
  const response = await apiClient.patch<GradeSubjectRequirement>(
    `/api/v1/grade-subject-requirements/${requirementId}`,
    data,
  );
  return response.data;
}

export async function remove(requirementId: number): Promise<void> {
  await apiClient.delete(`/api/v1/grade-subject-requirements/${requirementId}`);
}
