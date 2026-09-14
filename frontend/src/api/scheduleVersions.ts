import { apiClient } from "./client";
import type {
  ScheduleVersion,
  ScheduleVersionCreate,
  ScheduleVersionUpdate,
} from "../types/scheduleVersion";
import type {
  GenerateLessonsResponse,
  RunSchedulerSuccessResponse,
} from "../types/scheduler";

// Mirrors backend/app/routers/schedule_version.py's 5 CRUD endpoints -- see
// teachers.ts for why create()/update()/remove() exist even though this
// page only calls list()/create() so far.

export async function list(skip = 0, limit = 100): Promise<ScheduleVersion[]> {
  const response = await apiClient.get<ScheduleVersion[]>(
    "/api/v1/schedule-versions/",
    { params: { skip, limit } },
  );
  return response.data;
}

export async function get(versionId: number): Promise<ScheduleVersion> {
  const response = await apiClient.get<ScheduleVersion>(
    `/api/v1/schedule-versions/${versionId}`,
  );
  return response.data;
}

export async function create(
  data: ScheduleVersionCreate,
): Promise<ScheduleVersion> {
  const response = await apiClient.post<ScheduleVersion>(
    "/api/v1/schedule-versions/",
    data,
  );
  return response.data;
}

export async function update(
  versionId: number,
  data: ScheduleVersionUpdate,
): Promise<ScheduleVersion> {
  const response = await apiClient.patch<ScheduleVersion>(
    `/api/v1/schedule-versions/${versionId}`,
    data,
  );
  return response.data;
}

export async function remove(versionId: number): Promise<void> {
  await apiClient.delete(`/api/v1/schedule-versions/${versionId}`);
}

// --- Semantic sub-actions (not standard CRUD) ---

export async function generateLessons(
  versionId: number,
): Promise<GenerateLessonsResponse> {
  const response = await apiClient.post<GenerateLessonsResponse>(
    `/api/v1/schedule-versions/${versionId}/generate-lessons`,
  );
  return response.data;
}

// Success (200) resolves with RunSchedulerSuccessResponse. Failure (422)
// rejects with an AxiosError whose response.data is a
// RunSchedulerFailureResponse -- the caller (SchedulerConsole.tsx)
// distinguishes the two via the promise's resolve/reject, not a return
// value, matching how every other API module here surfaces errors.
export async function runScheduler(
  versionId: number,
): Promise<RunSchedulerSuccessResponse> {
  const response = await apiClient.post<RunSchedulerSuccessResponse>(
    `/api/v1/schedule-versions/${versionId}/run-scheduler`,
  );
  return response.data;
}
