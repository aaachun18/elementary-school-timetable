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
