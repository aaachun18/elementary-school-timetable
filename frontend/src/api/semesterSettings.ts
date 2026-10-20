import { apiClient } from "./client";
import type {
  GradeTimeSlots,
  SemesterTeacher,
  SemesterTeacherEntry,
} from "../types/semesterSettings";

// Task 98: backend/app/routers/semester_settings.py and the grade router's
// default-time-slots -- the wizard's per-semester settings.

export async function listTeachers(semesterId: number): Promise<SemesterTeacher[]> {
  const response = await apiClient.get<SemesterTeacher[]>(
    `/api/v1/semesters/${semesterId}/teachers`,
  );
  return response.data;
}

// The complete list: a teacher left out no longer takes part.
export async function replaceTeachers(
  semesterId: number,
  teachers: SemesterTeacherEntry[],
): Promise<SemesterTeacher[]> {
  const response = await apiClient.put<SemesterTeacher[]>(
    `/api/v1/semesters/${semesterId}/teachers`,
    { teachers },
  );
  return response.data;
}

export async function listGradeTimeSlots(semesterId: number): Promise<GradeTimeSlots[]> {
  const response = await apiClient.get<GradeTimeSlots[]>(
    `/api/v1/semesters/${semesterId}/grade-time-slots`,
  );
  return response.data;
}

export async function replaceGradeTimeSlots(
  semesterId: number,
  gradeId: number,
  timeSlotIds: number[],
): Promise<GradeTimeSlots> {
  const response = await apiClient.put<GradeTimeSlots>(
    `/api/v1/semesters/${semesterId}/grades/${gradeId}/time-slots`,
    { time_slot_ids: timeSlotIds },
  );
  return response.data;
}

export async function defaultGradeTimeSlots(gradeId: number): Promise<number[]> {
  const response = await apiClient.get<number[]>(`/api/v1/grades/${gradeId}/default-time-slots`);
  return response.data;
}
