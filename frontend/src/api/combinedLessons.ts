import { apiClient } from "./client";
import type {
  CombinedLesson,
  CombinedLessonCreate,
  CombinedLessonFields,
} from "../types/combinedLesson";

// Mirrors backend/app/routers/combined_lesson.py -- 共同排課 of a 排課紀錄.

export async function list(versionId: number): Promise<CombinedLesson[]> {
  const response = await apiClient.get<CombinedLesson[]>("/api/v1/combined-lessons/", {
    params: { schedule_version_id: versionId },
  });
  return response.data;
}

export async function create(data: CombinedLessonCreate): Promise<CombinedLesson> {
  const response = await apiClient.post<CombinedLesson>("/api/v1/combined-lessons/", data);
  return response.data;
}

export async function update(combinedLessonId: number, data: CombinedLessonFields): Promise<CombinedLesson> {
  const response = await apiClient.put<CombinedLesson>(
    `/api/v1/combined-lessons/${combinedLessonId}`,
    data,
  );
  return response.data;
}

export async function remove(combinedLessonId: number): Promise<void> {
  await apiClient.delete(`/api/v1/combined-lessons/${combinedLessonId}`);
}
