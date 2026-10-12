import { apiClient } from "./client";
import type { TimeSlot } from "../types/timeSlot";

// GET /api/v1/teachers/{id}/unavailable-slots -- same semantic-sub-resource
// reasoning as teacherSubjects.ts. Returns full TimeSlot objects (not just
// ids), which is exactly what the UI needs to show "星期三第 3 節" instead
// of a bare time_slot_id.
export async function listByTeacher(teacherId: number): Promise<TimeSlot[]> {
  const response = await apiClient.get<TimeSlot[]>(
    `/api/v1/teachers/${teacherId}/unavailable-slots`,
  );
  return response.data;
}

// POST /api/v1/teachers/{id}/unavailable-slots -- Task 46. Same error
// shapes as teacherSubjects.ts's create() (409 duplicate / 422 invalid
// reference), both already generic and Chinese.
export async function create(
  teacherId: number,
  timeSlotId: number,
): Promise<TimeSlot> {
  const response = await apiClient.post<TimeSlot>(
    `/api/v1/teachers/${teacherId}/unavailable-slots`,
    { time_slot_id: timeSlotId },
  );
  return response.data;
}

export async function remove(teacherId: number, timeSlotId: number): Promise<void> {
  await apiClient.delete(
    `/api/v1/teachers/${teacherId}/unavailable-slots/${timeSlotId}`,
  );
}
