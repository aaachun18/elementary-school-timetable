import { apiClient } from "./client";
import type {
  ScheduleVersion,
  ScheduleVersionCopy,
  ScheduleVersionCreate,
  ScheduleVersionUpdate,
} from "../types/scheduleVersion";
import type {
  ChangeRoomRequest,
  ChangeRoomResult,
  GenerateLessonsResponse,
  MoveCandidatesResult,
  MoveLessonRequest,
  PlaceCandidatesResult,
  PlaceLessonRequest,
  PlaceLessonResult,
  PreflightResult,
  RunSchedulerSuccessResponse,
  ScheduleAdjustmentResult,
  ScheduleCheckResult,
  SwapLessonsRequest,
  TeacherReassignmentRequest,
  TeacherReassignmentResult,
  UnscheduledLessonsResult,
  UnscheduleLessonRequest,
} from "../types/scheduler";

// Mirrors backend/app/routers/schedule_version.py -- v3: 排課紀錄 (newest
// first; manual edits' working copies are never listed).

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

// Only the 備註 changes this way.
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

// Success (200) resolves with RunSchedulerSuccessResponse -- the record is
// then 自動排課. Failure (422) rejects with an AxiosError whose
// response.data is a RunSchedulerFailureResponse (the record stays
// 尚未排課) -- the caller distinguishes the two via the promise's
// resolve/reject, not a return value, matching how every other API module
// here surfaces errors.
// 排課前檢查: read only, nothing written (wizard step 6).
export async function preflight(versionId: number): Promise<PreflightResult> {
  const response = await apiClient.get<PreflightResult>(`/api/v1/schedule-versions/${versionId}/preflight`);
  return response.data;
}

export async function runScheduler(
  versionId: number,
): Promise<RunSchedulerSuccessResponse> {
  const response = await apiClient.post<RunSchedulerSuccessResponse>(
    `/api/v1/schedule-versions/${versionId}/run-scheduler`,
  );
  return response.data;
}

// --- v3: publishing, copying and manual editing a record ---

// 發布此課表: the semester's one published record from now on (the one
// published before goes back to an ordinary record) -- reload the whole
// list afterwards, not just this record.
export async function publish(versionId: number): Promise<ScheduleVersion> {
  const response = await apiClient.post<ScheduleVersion>(
    `/api/v1/schedule-versions/${versionId}/publish`,
  );
  return response.data;
}

// 取消發布: the semester has no published record until another one is
// published (the record and its timetable stay).
export async function unpublish(versionId: number): Promise<ScheduleVersion> {
  const response = await apiClient.post<ScheduleVersion>(
    `/api/v1/schedule-versions/${versionId}/unpublish`,
  );
  return response.data;
}

// 複製此課表: settings and timetable into a new 複製自編號 x record of any
// semester of the same academic year (null: the source's own).
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

// 複製此次排課設定: a new 尚未排課 record with the same settings.
export async function copySettings(versionId: number): Promise<ScheduleVersion> {
  const response = await apiClient.post<ScheduleVersion>(
    `/api/v1/schedule-versions/${versionId}/copy-settings`,
  );
  return response.data;
}

// 手動編輯課表: a fresh working copy (EDITING) every adjustment then
// changes. Leaving without saving: remove() the working copy.
export async function startEditing(versionId: number): Promise<ScheduleVersion> {
  const response = await apiClient.post<ScheduleVersion>(
    `/api/v1/schedule-versions/${versionId}/edit`,
  );
  return response.data;
}

// 儲存課表 (on the working copy): resolves with the record the edit was
// saved as -- the 手動排課 record itself, or a new 手動排課 record.
export async function saveEditing(workingCopyId: number): Promise<ScheduleVersion> {
  const response = await apiClient.post<ScheduleVersion>(
    `/api/v1/schedule-versions/${workingCopyId}/save`,
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

// --- Task 69: manual adjustment of a working copy's timetable (教學組長
// only). Both save unless dry_run is true; conflicts never block, they're
// reported in the response's `check`. ---

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

// 移出課表 (v3: only in a manual edit's working copy): the lesson, with its
// whole 連堂 block, becomes an unscheduled lesson again.
export async function unscheduleLesson(
  versionId: number,
  body: UnscheduleLessonRequest,
): Promise<ScheduleAdjustmentResult> {
  const response = await apiClient.post<ScheduleAdjustmentResult>(
    `/api/v1/schedule-versions/${versionId}/unschedule-lesson`,
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
// teacher -- v3: only in the working copy of a copied timetable. Only
// refused for a missing record, any other timetable, a requirement of
// another record, or an inactive new teacher; conflicts are reported in
// `check`, never blocked. ---

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

// Task 84: read-only "what if" of moving / swapping one lesson into every
// time slot (Task 83). `signal` lets the caller abandon a request whose
// lesson is no longer selected or dragged.
export async function moveCandidates(
  versionId: number,
  scheduleId: number,
  signal?: AbortSignal,
): Promise<MoveCandidatesResult> {
  const response = await apiClient.get<MoveCandidatesResult>(
    `/api/v1/schedule-versions/${versionId}/move-candidates/${scheduleId}`,
    { signal },
  );
  return response.data;
}

// --- Task 93: unscheduled lessons (backend Task 92; ADMIN only). ---

// Lessons of the record with no Schedule row in its timetable (any
// record).
export async function unscheduledLessons(versionId: number): Promise<UnscheduledLessonsResult> {
  const response = await apiClient.get<UnscheduledLessonsResult>(
    `/api/v1/schedule-versions/${versionId}/unscheduled-lessons`,
  );
  return response.data;
}

// Read-only "what if" of placing one lesson (and the unplaced rest of its
// block) into every time slot, with this teacher and room (working copy
// only).
// teacherId null: the requirement's required teacher (none -> 409
// TEACHER_REQUIRED); roomId null: the backend's default room.
export async function placeCandidates(
  versionId: number,
  lessonId: number,
  teacherId: number | null,
  roomId: number | null,
  signal?: AbortSignal,
): Promise<PlaceCandidatesResult> {
  const params: Record<string, number> = {};
  if (teacherId !== null) {
    params.teacher_id = teacherId;
  }
  if (roomId !== null) {
    params.room_id = roomId;
  }
  const response = await apiClient.get<PlaceCandidatesResult>(
    `/api/v1/schedule-versions/${versionId}/place-candidates/${lessonId}`,
    { params, signal },
  );
  return response.data;
}

// Saves unless dry_run is true; conflicts never block, they're in `check`.
export async function placeLesson(
  versionId: number,
  body: PlaceLessonRequest,
): Promise<PlaceLessonResult> {
  const response = await apiClient.post<PlaceLessonResult>(
    `/api/v1/schedule-versions/${versionId}/place-lesson`,
    body,
  );
  return response.data;
}

// --- Task 95: change the room of scheduled lessons in a working copy
// (教學組長 only). Saves unless dry_run is true; conflicts are reported in
// `check`.
export async function changeRoom(versionId: number, body: ChangeRoomRequest): Promise<ChangeRoomResult> {
  const response = await apiClient.post<ChangeRoomResult>(
    `/api/v1/schedule-versions/${versionId}/change-room`,
    body,
  );
  return response.data;
}
