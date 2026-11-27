import { apiClient } from "./client";
import type { OwnPasswordChange, Profile } from "../types/me";

// 個人資料維護 (backend/app/routers/me.py): any logged-in account.

export async function getProfile(): Promise<Profile> {
  const response = await apiClient.get<Profile>("/api/v1/me");
  return response.data;
}

// 教學組長 / 一般老師 only: the name their timetables show.
export async function updateName(name: string): Promise<Profile> {
  const response = await apiClient.patch<Profile>("/api/v1/me", { name });
  return response.data;
}

export async function changePassword(data: OwnPasswordChange): Promise<void> {
  await apiClient.patch("/api/v1/me/password", data);
}
