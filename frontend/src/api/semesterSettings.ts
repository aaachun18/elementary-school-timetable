import { apiClient } from "./client";
import type {
  GradeTimeSlots,
  SemesterTeacher,
  SemesterTeacherEntry,
} from "../types/semesterSettings";

// Task 98: backend/app/routers/semester_settings.py and the grade router's
// default-time-slots -- a 排課紀錄's settings (v3: one set per record,
// changeable only while it is 尚未排課).

export async function listTeachers(versionId: number): Promise<SemesterTeacher[]> {
  const response = await apiClient.get<SemesterTeacher[]>(
    `/api/v1/schedule-versions/${versionId}/teachers`,
  );
  return response.data;
}

// The complete list: a teacher left out no longer takes part.
export async function replaceTeachers(
  versionId: number,
  teachers: SemesterTeacherEntry[],
): Promise<SemesterTeacher[]> {
  const response = await apiClient.put<SemesterTeacher[]>(
    `/api/v1/schedule-versions/${versionId}/teachers`,
    { teachers },
  );
  return response.data;
}

export async function listGradeTimeSlots(versionId: number): Promise<GradeTimeSlots[]> {
  const response = await apiClient.get<GradeTimeSlots[]>(
    `/api/v1/schedule-versions/${versionId}/grade-time-slots`,
  );
  return response.data;
}

export async function replaceGradeTimeSlots(
  versionId: number,
  gradeId: number,
  timeSlotIds: number[],
): Promise<GradeTimeSlots> {
  const response = await apiClient.put<GradeTimeSlots>(
    `/api/v1/schedule-versions/${versionId}/grades/${gradeId}/time-slots`,
    { time_slot_ids: timeSlotIds },
  );
  return response.data;
}

export async function defaultGradeTimeSlots(gradeId: number): Promise<number[]> {
  const response = await apiClient.get<number[]>(`/api/v1/grades/${gradeId}/default-time-slots`);
  return response.data;
}
