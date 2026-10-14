import { apiClient } from "./client";
import type {
  Schedule,
  ScheduleCreate,
  ScheduleListFilters,
  ScheduleUpdate,
} from "../types/schedule";

// Mirrors backend/app/routers/schedule.py's 5 endpoints -- see teachers.ts
// for why create()/update()/remove() exist even though Task 34 only calls
// list().
//
// Task 67: `filters` maps to GET /api/v1/schedules/'s optional
// schedule_version_id (Task 66; results ordered by id, so skip/limit pages
// are stable). Omitted -> every row the current user may see, exactly as
// before. axios drops undefined params, so an empty filters object sends
// only skip/limit.

export async function list(
  skip = 0,
  limit = 100,
  filters: ScheduleListFilters = {},
): Promise<Schedule[]> {
  const response = await apiClient.get<Schedule[]>("/api/v1/schedules/", {
    params: { skip, limit, ...filters },
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
