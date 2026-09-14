import { apiClient } from "./client";
import type { Schedule, ScheduleCreate, ScheduleUpdate } from "../types/schedule";

// Mirrors backend/app/routers/schedule.py's 5 endpoints -- see teachers.ts
// for why create()/update()/remove() exist even though Task 34 only calls
// list().
//
// GET /api/v1/schedules/ does NOT support filtering by schedule_version_id
// (only skip/limit) -- confirmed by reading routers/schedule.py, not
// guessed. list() therefore always fetches everything and the caller
// (useTimetableData.ts) filters by schedule_version_id itself. `limit`
// defaults to 100 like every other list() here, but the schedules table
// alone already holds 100+ rows in this project's dev database (each
// run-scheduler call adds one row per Lesson), so useTimetableData.ts
// passes an explicitly larger limit rather than relying on this default.

export async function list(skip = 0, limit = 100): Promise<Schedule[]> {
  const response = await apiClient.get<Schedule[]>("/api/v1/schedules/", {
    params: { skip, limit },
  });
  return response.data;
}

export async function get(scheduleId: number): Promise<Schedule> {
  const response = await apiClient.get<Schedule>(`/api/v1/schedules/${scheduleId}`);
  return response.data;
}

export async function create(data: ScheduleCreate): Promise<Schedule> {
  const response = await apiClient.post<Schedule>("/api/v1/schedules/", data);
  return response.data;
}

export async function update(
  scheduleId: number,
  data: ScheduleUpdate,
): Promise<Schedule> {
  const response = await apiClient.patch<Schedule>(
    `/api/v1/schedules/${scheduleId}`,
    data,
  );
  return response.data;
}

export async function remove(scheduleId: number): Promise<void> {
  await apiClient.delete(`/api/v1/schedules/${scheduleId}`);
}
