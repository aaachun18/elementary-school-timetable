import { apiClient } from "./client";
import type { TimeSlot, TimeSlotBulkUpdateItem, TimeSlotUpdate } from "../types/timeSlot";

// Mirrors backend/app/routers/time_slot.py. No create/remove: a school's
// grid is built with the school and fixed.

export async function list(skip = 0, limit = 100): Promise<TimeSlot[]> {
  const response = await apiClient.get<TimeSlot[]>("/api/v1/time-slots/", {
    params: { skip, limit },
  });
  return response.data;
}

export async function get(timeSlotId: number): Promise<TimeSlot> {
  const response = await apiClient.get<TimeSlot>(
    `/api/v1/time-slots/${timeSlotId}`,
  );
  return response.data;
}

export async function update(
  timeSlotId: number,
  data: TimeSlotUpdate,
): Promise<TimeSlot> {
  const response = await apiClient.patch<TimeSlot>(
    `/api/v1/time-slots/${timeSlotId}`,
    data,
  );
  return response.data;
}

// Several slots at once, all or nothing; returns the school's whole grid.
export async function updateMany(items: TimeSlotBulkUpdateItem[]): Promise<TimeSlot[]> {
  const response = await apiClient.patch<TimeSlot[]>("/api/v1/time-slots/", {
    time_slots: items,
  });
  return response.data;
}
