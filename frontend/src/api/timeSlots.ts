import { apiClient } from "./client";
import type { TimeSlot, TimeSlotCreate, TimeSlotUpdate } from "../types/timeSlot";

// Mirrors backend/app/routers/time_slot.py's 5 endpoints -- see teachers.ts
// for why create()/update()/remove() exist even though Phase A only calls
// list()/get().

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

export async function create(data: TimeSlotCreate): Promise<TimeSlot> {
  const response = await apiClient.post<TimeSlot>("/api/v1/time-slots/", data);
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

export async function remove(timeSlotId: number): Promise<void> {
  await apiClient.delete(`/api/v1/time-slots/${timeSlotId}`);
}
