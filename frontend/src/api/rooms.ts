import { apiClient } from "./client";
import type { Room, RoomCreate, RoomUpdate } from "../types/room";

// Mirrors backend/app/routers/room.py's 5 endpoints -- see teachers.ts for
// why create()/update()/remove() exist even though Phase A only calls
// list()/get().

export async function list(skip = 0, limit = 100): Promise<Room[]> {
  const response = await apiClient.get<Room[]>("/api/v1/rooms/", {
    params: { skip, limit },
  });
  return response.data;
}

export async function get(roomId: number): Promise<Room> {
  const response = await apiClient.get<Room>(`/api/v1/rooms/${roomId}`);
  return response.data;
}

export async function create(data: RoomCreate): Promise<Room> {
  const response = await apiClient.post<Room>("/api/v1/rooms/", data);
  return response.data;
}

export async function update(roomId: number, data: RoomUpdate): Promise<Room> {
  const response = await apiClient.patch<Room>(`/api/v1/rooms/${roomId}`, data);
  return response.data;
}

export async function remove(roomId: number): Promise<void> {
  await apiClient.delete(`/api/v1/rooms/${roomId}`);
}
