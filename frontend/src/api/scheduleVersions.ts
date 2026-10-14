import { apiClient } from "./client";
import type {
  ScheduleVersion,
  ScheduleVersionCopy,
  ScheduleVersionCreate,
  ScheduleVersionUpdate,
} from "../types/scheduleVersion";
import type {
  GenerateLessonsResponse,
  MoveLessonRequest,
  RunSchedulerSuccessResponse,
  ScheduleAdjustmentResult,
  ScheduleCheckResult,
  SwapLessonsRequest,
  TeacherReassignmentRequest,
  TeacherReassignmentResult,
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

// --- Task 67: version management (Task 62/64 backend rules) ---

// DRAFT or ARCHIVED -> PUBLISHED. The backend archives the semester's
// previously PUBLISHED version in the same transaction, so callers should
// reload the whole version list afterwards, not just this one version.
export async function publish(versionId: number): Promise<ScheduleVersion> {
  return update(versionId, { status: "PUBLISHED" });
}

// PUBLISHED -> ARCHIVED. Leaves the semester with no PUBLISHED version.
export async function unpublish(versionId: number): Promise<ScheduleVersion> {
  return update(versionId, { status: "ARCHIVED" });
}

// Omitted/null targetSemesterId = same-semester copy. Resolves with the new
// DRAFT version (201).
export async function copy(
  versionId: number,
  targetSemesterId: number | null = null,
): Promise<ScheduleVersion> {
  const body: ScheduleVersionCopy = { target_semester_id: targetSemesterId };
  const response = await apiClient.post<ScheduleVersion>(
    `/api/v1/schedule-versions/${versionId}/copy`,
    body,
  );
  return response.data;
}

// Task 68: read-only Hard Constraint check of the version's current
// timetable (any status). Conflicts are reported in the 200 response, never
// as an error -- a rejection here means the check itself couldn't run.
export async function check(versionId: number): Promise<ScheduleCheckResult> {
  const response = await apiClient.get<ScheduleCheckResult>(
    `/api/v1/schedule-versions/${versionId}/check`,
  );
  return response.data;
}

// --- Task 69: manual adjustment of a DRAFT's timetable (ADMIN only). Both
// save unless dry_run is true; conflicts never block, they're reported in
// the response's `check`. ---

export async function moveLesson(
  versionId: number,
  body: MoveLessonRequest,
): Promise<ScheduleAdjustmentResult> {
  const response = await apiClient.post<ScheduleAdjustmentResult>(
    `/api/v1/schedule-versions/${versionId}/move-lesson`,
    body,
  );
  return response.data;
}

export async function swapLessons(
  versionId: number,
  body: SwapLessonsRequest,
): Promise<ScheduleAdjustmentResult> {
  const response = await apiClient.post<ScheduleAdjustmentResult>(
    `/api/v1/schedule-versions/${versionId}/swap-lessons`,
    body,
  );
  return response.data;
}

// --- Task 70: reassign one course (ClassSubjectRequirement) to a new
// teacher in a DRAFT (ADMIN only). Only refused for a missing record, a
// locked version, a requirement of another semester, or an inactive new
// teacher; conflicts are reported in `check`, never blocked. ---

export interface ReassignTeacherParams {
  requirementId: number;
  newTeacherId: number;
  dryRun: boolean;
}

export async function reassignTeacher(
  versionId: number,
  { requirementId, newTeacherId, dryRun }: ReassignTeacherParams,
): Promise<TeacherReassignmentResult> {
  const body: TeacherReassignmentRequest = {
    class_subject_requirement_id: requirementId,
    new_teacher_id: newTeacherId,
    dry_run: dryRun,
  };
  const response = await apiClient.post<TeacherReassignmentResult>(
    `/api/v1/schedule-versions/${versionId}/reassign-teacher`,
    body,
  );
  return response.data;
}
