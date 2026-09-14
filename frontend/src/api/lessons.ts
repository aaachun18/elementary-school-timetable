import { apiClient } from "./client";
import type { Lesson, LessonFixTimeSlot } from "../types/lesson";

// NOT a full 5-set, deliberately: backend/app/routers/lesson.py only has
// GET list, GET one, and PATCH fix-time-slot -- there is no POST/standard-
// PATCH/DELETE for Lesson at all (rows only come from generate-lessons).
// Writing create()/update()/remove() stubs here would point at endpoints
// that don't exist and would 404 if ever called, which defeats the whole
// point of the 5-set convention (every function maps to a real endpoint) --
// see teachers.ts for that convention's normal shape, where the backend
// genuinely does have all 5.

export async function list(skip = 0, limit = 100): Promise<Lesson[]> {
  const response = await apiClient.get<Lesson[]>("/api/v1/lessons/", {
    params: { skip, limit },
  });
  return response.data;
}

export async function get(lessonId: number): Promise<Lesson> {
  const response = await apiClient.get<Lesson>(`/api/v1/lessons/${lessonId}`);
  return response.data;
}

export async function fixTimeSlot(
  lessonId: number,
  data: LessonFixTimeSlot,
): Promise<Lesson> {
  const response = await apiClient.patch<Lesson>(
    `/api/v1/lessons/${lessonId}/fix-time-slot`,
    data,
  );
  return response.data;
}
