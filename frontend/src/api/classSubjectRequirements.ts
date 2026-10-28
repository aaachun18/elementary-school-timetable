import { apiClient } from "./client";
import type {
  ClassSubjectRequirement,
  ClassSubjectRequirementCreate,
  ClassSubjectRequirementListFilters,
  ClassSubjectRequirementUpdate,
  LessonPatternItem,
  RequirementSyncResult,
} from "../types/classSubjectRequirement";

// Mirrors backend/app/routers/class_subject_requirement.py's 5 endpoints --
// see teachers.ts for why create()/update()/remove() exist even though
// Task 31 only calls list().

// `filters.schedule_version_id` narrows to one 排課紀錄's requirements;
// omitted -> every requirement.
export async function list(
  skip = 0,
  limit = 100,
  filters: ClassSubjectRequirementListFilters = {},
): Promise<ClassSubjectRequirement[]> {
  const response = await apiClient.get<ClassSubjectRequirement[]>(
    "/api/v1/class-subject-requirements/",
    { params: { skip, limit, ...filters } },
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

// The wizard's 科目需求 step: the (尚未排課) record's requirements follow
// the school's 科目需求 (學校資料) -- created, resized or removed.
export async function syncWithSchool(versionId: number): Promise<RequirementSyncResult> {
  const response = await apiClient.post<RequirementSyncResult>(
    "/api/v1/class-subject-requirements/sync",
    { schedule_version_id: versionId },
  );
  return response.data;
}

// Task 103: 「複製此連堂設定至所有同年級班級」 -- several requirements' 連堂樣式
// in one transaction (all saved, or none); returns the saved rows.
export async function updateLessonPatterns(
  items: readonly LessonPatternItem[],
): Promise<ClassSubjectRequirement[]> {
  const response = await apiClient.patch<ClassSubjectRequirement[]>(
    "/api/v1/class-subject-requirements/lesson-patterns",
    { items },
  );
  return response.data;
}
